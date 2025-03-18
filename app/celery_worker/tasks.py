from app.celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.database.database import SessionLocal
from app.database.models import User, Post, ProfileComparison, Profile, Blog, BlogProfileComparison, Schedule, Prompt
from celery.exceptions import SoftTimeLimitExceeded
from datetime import datetime, timezone
import asyncio
import logging



@celery_app.task(bind=True)
def draft_draft(self, url:str, prompt_id:int, user_id:int):
    post_id = None
    try:
        with SessionLocal() as db:
            post = Post(
                user_id=user_id,
                url=url,
                status=Post.PROCESSING,
                created_at_utc=datetime.now(timezone.utc)
            )
            db.add(post)
            db.commit()
            db.flush()
            post_id = post.id
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            post.markdown_text = processor.draft(url=url,prompt_id=prompt_id)
            post.plain_text = processor.convert_markdown_to_plain_text(post.markdown_text)
            post.thread_list_text = processor.convert_markdown_to_tweet_thread(post.markdown_text)
            post.status = Post.GENERATED
            db.commit()
    except Exception as e:
        with SessionLocal() as db:
            post = db.query(Post).get(post_id)
            post.status = Post.FAILED
            post.error_message = str(e)
            db.commit()
        logging.error(f"Error drafting draft: {str(e)}")
        raise e

# Is called by the profile_compare route and creates a profile_comparison object that judges whether or not the url fits the profile.
@celery_app.task(bind=True)
def compare_profile_task(self, url: str, user_id: int):
    with SessionLocal() as db:
        try:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            user = db.query(User).get(user_id)
            profile_comparison = ProfileComparison(
                    user_id=user_id,
                    url=url,
                    status=ProfileComparison.PROCESSING,
                    created_at=datetime.utcnow(),
                    profile_interests=profile.interests_description 
                )
            db.add(profile_comparison)
            db.commit()
            db.flush()

            processor = SyncAsyncContentProcessor(user)
            short_summary = processor.write_small_summary(profile_comparison.url)
            relevance_result = processor.is_article_relevant_short_summary(
                short_summary=short_summary
            )

            profile_comparison.comparison_result = relevance_result
            profile_comparison.short_summary = short_summary
            profile_comparison.status = ProfileComparison.COMPLETED
        except Exception as e:
            profile_comparison.error_message= str(e)
            profile_comparison.status = ProfileComparison.FAILED
            raise e
        db.commit()

@celery_app.task(bind=True)
def comparison_draft(self, user_id:int, comparison_id:int, prompt_id:int):
    post_id = None
    try: 
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            comparison.status = BlogProfileComparison.STATUS_DRAFTING
            url = comparison.url
            user = db.query(User).get(user_id)
            post = Post(
                user_id=user_id,
                url=url,
                status=Post.PROCESSING,
                created_at_utc=datetime.now(timezone.utc),
                blog_comparison_id = comparison_id
            )
            db.add(post)
            db.commit()
            db.flush() # Flushes pending changes to the DB so that post.id is populated.
            post_id = post.id
            processor = SyncAsyncContentProcessor(user)
            post.markdown_text = processor.draft(url,prompt_id)
            post.plain_text = processor.convert_markdown_to_plain_text(post.markdown_text)
            post.thread_list_text = processor.convert_markdown_to_tweet_thread(post.markdown_text)
            post.status = Post.GENERATED
            db.commit()
            db.flush()
            # Get a fresh comparison object from the database in order to update it.
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            comparison.post_id = post.id
            comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST
            db.commit()
    except Exception as e:
        logging.error(f"Error processing comparison {comparison_id}  : {str(e)}")
        with SessionLocal() as db:
            post = db.query(Post).get(post_id)
            post.status = Post.FAILED
            post.error_message = str(e)
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            comparison.status = BlogProfileComparison.STATUS_FAILED_ON_DRAFT
            comparison.error_message = str(e)
            db.commit()
        raise e

@celery_app.task(bind=True)
def blog_analyse(self, url: str, user_id: int, schedule_id: int = None):
    try:
        blog_id = None
        with SessionLocal() as db:
            if schedule_id is not None:
                schedule = db.query(Schedule).get(schedule_id)
                if schedule:
                    schedule.last_run_at = datetime.utcnow()    
                    db.commit()
        with SessionLocal() as db:
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            blog = Blog(
                    url=url,
                    user_id=user_id,
                    status=Blog.PROCESSING, 
                    created_at=datetime.utcnow(),
                    schedule_id=schedule_id
                )
            db.add(blog)
            db.commit()
            blog_id = blog.id
        articles = processor.extract_all_articles_from_page(url)
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.number_of_articles = len(articles)
            db.commit()
        logging.info(f"Extracted {len(articles)} articles from {url} and added to database")
        
        with SessionLocal() as db:
            existing_comparisons = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.user_id == user_id
            ).all()
            # Dictionary that includes the oldest blog_id for each url 
            processed_urls = {}
            for comp in existing_comparisons:
                if comp.url not in processed_urls or comp.created_at < processed_urls[comp.url]['created_at']:
                    processed_urls[comp.url] = {
                        'blog_id': comp.blog_id,
                        'created_at': comp.created_at,
                        'short_summary': comp.short_summary
                    }
        new_comparisons = {url: title for url, title in articles.items() if url not in processed_urls}
        already_processed = {url: {'title': title, 'past_blog_id': processed_urls[url]['blog_id'], 'short_summary': processed_urls[url]['short_summary']} 
                            for url, title in articles.items() if url in processed_urls}

        new_comparisons_ids = []
        with SessionLocal() as db:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            for url, title in new_comparisons.items():
                comparison = BlogProfileComparison( 
                    url=url,
                    blog_id=blog_id,
                    user_id=user_id,
                    schedule_id=schedule_id,
                    profile_interests=profile.interests_description,
                    status=BlogProfileComparison.STATUS_COMPARING,
                    title=title
                )
                db.add(comparison)
                db.flush()
                new_comparisons_ids.append(comparison.id)
                db.commit()
            
            for url, data in already_processed.items():
                comparison = BlogProfileComparison(
                    url=url,
                    blog_id=blog_id,
                    user_id=user_id,
                    schedule_id=schedule_id,
                    profile_interests=profile.interests_description,
                    status=BlogProfileComparison.STATUS_PROCESSED_IN_PAST_BLOG,
                    past_blog_id=data['past_blog_id'],
                    short_summary=data['short_summary'],
                    title=data['title']
                )
                db.add(comparison)
                db.flush()
                db.commit()

        fitting_articles = 0
        if new_comparisons:
            short_summaries = []
            for url in new_comparisons.keys():
                short_summary = processor.write_small_summary(url)
                short_summaries.append(short_summary)
            logging.info(f"Wrote short summaries for {len(new_comparisons)} articles")
            with SessionLocal() as db:
                for comp_id, short_summary in zip(new_comparisons_ids, short_summaries):
                    comparison = db.query(BlogProfileComparison).get(comp_id)
                    if not short_summary:
                        comparison.status = BlogProfileComparison.STATUS_FAILED_ON_COMPARISON
                        comparison.error_message = 'Failed to get a short summary for the comparison'
                    else:
                        comparison.short_summary = short_summary
                db.commit()


            with SessionLocal() as db:
                user = db.query(User).get(user_id)
                processor = SyncAsyncContentProcessor(user)
                blog_comparisons = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.blog_id == blog_id,
                    BlogProfileComparison.status == BlogProfileComparison.STATUS_COMPARING
                ).all()
                for blog_comparison in blog_comparisons:
                    try:
                        short_summary = blog_comparison.short_summary
                        if not short_summary:
                            continue
                        relevance_result = processor.is_article_relevant_short_summary(short_summary)
                        blog_comparison.comparison_result = True if relevance_result else False
                        if relevance_result:
                            blog_comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_DRAFT
                            fitting_articles += 1
                        else:
                            blog_comparison.status = BlogProfileComparison.STATUS_DEEMED_NOT_RELEVANT
                    except Exception as e:
                        blog_comparison.status = BlogProfileComparison.STATUS_FAILED_ON_COMPARISON
                        blog_comparison.error_message =str(e)
                        blog_comparison.comparison_result = None
                        logging.error(f"Failed to process comparison for URL {blog_comparison.url}: {str(e)}")
                    db.commit()
                logging.info(f"Compared {len(blog_comparisons)} articles to the user profile")
        
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.COMPLETED
            blog.number_of_fitting_articles = fitting_articles
            db.commit()
    except SoftTimeLimitExceeded:
        logging.error(f"Soft time limit exceeded for blog {blog_id} for user {user_id}")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.FAILED
            blog.error_message = "Task timed out, please contact support"
            db.commit()
        raise 
    except Exception as e:
        logging.error(f"Error in the second step of processing blog {blog_id} for user {user_id}: {str(e)}")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.FAILED
            blog.error_message = str(e)
            db.commit()
        raise e