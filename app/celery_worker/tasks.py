from app.celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.core.crawl4ai import ArticleCrawler
from app.database.database import SessionLocal
from app.database.models import User, Post, ProfileComparison, Profile, Blog, BlogProfileComparison

from datetime import datetime, timezone
import json
import asyncio
import logging


@celery_app.task(bind=True)
def generate_post(self,url:str,user_id:int):
    post_id = None
    try:
        with SessionLocal() as db:
            post = Post(
                user_id=user_id,
                url=url,
                status = Post.PROCESSING,
                created_at_utc=datetime.now(timezone.utc)
            )
            db.add(post)
            db.commit()
            db.flush() # Ensure that post.id is populated
            post_id = post.id
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            post_result = processor.generate_linkedin_informative_post_from_url(url)
            post.text = post_result
            post.status = Post.GENERATED
            db.commit()
    except Exception as e:
        with SessionLocal() as db:
            post = db.query(Post).get(post_id)
            post.status = Post.FAILED
            post.error_message = str(e)
            db.commit()
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
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                short_summary = loop.run_until_complete(processor.crawler.write_small_summary(profile_comparison.url))
                relevance_result = processor.is_article_relevant_short_summary(
                    short_summary=short_summary
                    )
            finally:
                loop.close()

            profile_comparison.comparison_result = relevance_result
            profile_comparison.short_summary = short_summary
            profile_comparison.status = ProfileComparison.COMPLETED
        except Exception as e:
            profile_comparison.error_message= str(e)
            profile_comparison.status = ProfileComparison.FAILED
            raise e
        db.commit()


@celery_app.task(bind=True)
def generate_linkedin_informative_post_from_comparison(self, user_id:int, comparison_id:int=None):
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
            logging.info(f"Created Post with id: {post.id}")
            logging.info(f"Starting generate_linkedin_informative_post_from_comparison task for comparison_id: {comparison_id}")
            processor = SyncAsyncContentProcessor(user)
            logging.info(f"Processing URL content for comparison {comparison_id}")
            post_result = processor.generate_linkedin_informative_post_from_url(url)
            post.text = post_result
            post.status = Post.GENERATED
            db.commit()
            db.flush()
            # Get a fresh comparison object from the database in order to update it.
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            comparison.post_id = post.id
            comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST
            db.commit()
            logging.info(f"Updated comparison {comparison_id} with post_id")
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
def redraft_linkedin_post_from_comparison(self, user_id:int, comparison_id:int=None):
    try:
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            comparison.status = BlogProfileComparison.STATUS_REDRAFTING
            url = comparison.url
            user = db.query(User).get(user_id)
            
            # Get the existing post
            post = db.query(Post).get(comparison.post_id)
            if not post:
                raise ValueError(f"No post found for comparison {comparison_id}")
            
            # Update post status to reprocessing
            post.status = Post.PROCESSING
            db.commit()
            
            # Generate new content
            processor = SyncAsyncContentProcessor(user)
            logging.info(f"Re-processing URL content for comparison {comparison_id}")
            post_result = processor.generate_linkedin_informative_post_from_url(url)
            
            # Update post with new content
            post.text = post_result
            post.status = Post.GENERATED
            comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST
            db.commit()
            
            logging.info(f"Successfully re-drafted post for comparison {comparison_id}")
            
    except Exception as e:
        logging.error(f"Error re-drafting post for comparison {comparison_id}: {str(e)}")
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            if comparison:
                comparison.status = BlogProfileComparison.STATUS_FAILED_ON_DRAFT
                comparison.error_message = str(e)
                
                # Update post status if it exists
                if comparison.post_id:
                    post = db.query(Post).get(comparison.post_id)
                    if post:
                        post.status = Post.FAILED
                        post.error_message = str(e)
# 1. Is called either from blogs_Handler.create_blog_analyse_session or directly from the scheduler
# 2. Creates a Blog Analysis, extracts all articles from the blog
# 3. Checks if Articles have been already processed before, if not, it finds out if they are relevant to the user profile
@celery_app.task(bind=True)
def blog_analyse(self, url: str, user_id: int, schedule_id: int = None):
    blog_id = None
    logging.info(f"Starting blog analysis task for user {user_id} with URL: {url}")
    try:
        with SessionLocal() as db:
            logging.info(f"Starting blogs of URL: {url}")
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
    except Exception as e:
        logging.error(f"Failed to initialize blog: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    
    logging.info(f"Starting extraction of articles from URL: {url}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            articles = loop.run_until_complete(processor.crawler.extract_all_articles_from_page(url))
            logging.info(f"Found {len(articles)} articles in Blog")
        finally:
            loop.close()

        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.number_of_articles = len(articles)
            db.commit()
        
        logging.info(f"Splitting the comparisons into already processed and unprocessed ones")
        with SessionLocal() as db:
            existing_comparisons = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.user_id == user_id
            ).all()
        processed_urls = {comp.url for comp in existing_comparisons}
        new_comparisons = {url: title for url, title in articles.items() if url not in processed_urls}
        already_processed = {url: title for url, title in articles.items() if url in processed_urls}

        logging.info(f"Found {len(new_comparisons)} new comparisons and {len(already_processed)} already processed comparisons")
        logging.info(f"Adding new comparisons to the database")
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
                    status=BlogProfileComparison.STATUS_COMPARING
                )
                db.add(comparison)
                db.flush()
                new_comparisons_ids.append(comparison.id)
                db.commit()
            
        logging.info(f"Added {len(new_comparisons_ids)} new comparisons")
        logging.info(f"Adding already processed comparisons to the database")
        with SessionLocal() as db:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            for url in already_processed:
                comparison = BlogProfileComparison(
                    url=url,
                    blog_id=blog_id,
                    user_id=user_id,
                    schedule_id=schedule_id,
                    profile_interests=profile.interests_description,
                    status=BlogProfileComparison.STATUS_PROCESSED_IN_PAST_BLOG
                )
                db.add(comparison)
            db.commit()

        fitting_articles = 0
        if new_comparisons:
            logging.info("Creating the small summaries for the new comparisons")
            short_summaries = []
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for url in new_comparisons.keys():
                    short_summary = loop.run_until_complete(processor.crawler.write_small_summary(url))
                    short_summaries.append(short_summary)
            finally:
                loop.close()

            logging.info("Updating comparisons with small summaries")
            with SessionLocal() as db:
                for comp_id, short_summary in zip(new_comparisons_ids, short_summaries):
                    comparison = db.query(BlogProfileComparison).get(comp_id)
                    if not short_summary:
                        comparison.status = BlogProfileComparison.STATUS_FAILED_ON_COMPARISON
                        comparison.error_message = 'Failed to get a short summary for the comparison'
                    else:
                        comparison.short_summary = short_summary
                db.commit()


            logging.info(f"Identifying if there are any relevant comparisons in blogs {blog_id} and updating the database")
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
        
        logging.info(f"Updating blogs Status and inserting relevant comparison count,there were {fitting_articles} fitting articles")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.COMPLETED
            blog.number_of_fitting_articles = fitting_articles
            db.commit()
    except Exception as e:
        logging.error(f"Error in the second step of processing blog {blog_id} for user {user_id}: {str(e)}")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.FAILED
            blog.error_message = str(e)
            db.commit()
        raise e
    