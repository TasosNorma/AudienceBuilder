from app.database.database import SessionLocal
from app.database.models import User, Post, BlogProfileComparison, Blog, Schedule, Profile
from app.core.content_processor import SyncAsyncContentProcessor
from datetime import datetime, timezone, timedelta
import logging


def blog_analyse( url: str, user_id: int, schedule_id: int = None):
    """
    Takes a url, user_id and schedule_id.
    Creates a blog object and extracts all articles from the url.
    Creates a blog profile comparison object for each article and checks if the article has been processed in the past.
    If it has, it marks the blog profile comparison as processed in past blog.
    If it has not, it creates a new blog profile comparison object and checks if the article is relevant.
    If it is not relevant, it marks the blog profile comparison as deemed not relevant.
    If it is relevant,
    - it writes the short summary and the article text to the blog profile comparison object.
    - it checks if the article is similar to any recent positive comparisons.
    - if it is, it marks the blog profile comparison as deemed not relevant.
    - if it is not, it marks the blog profile comparison as action pending to draft.
    - it updates the blog object with the number of fitting articles.

    Other features:
    - If the blog is triggered by a schedule, it updates the schedule last run at and attaches the schedule id to the blog object.
    - If the article was already processed in a past blog, it attaches the past blog id to the blog profile comparison object (the original one).
    """
    try:
        blog_id = None
        articles = []
        fitting_articles = 0
        extracted_data = []
        new_comparisons_ids = []
        processed_urls = {}
        new_comparisons = {}
        already_processed = {}

        # Check if it was triggered by schedule, create a blog and extract all articles.
        with SessionLocal() as db:
            if schedule_id is not None:
                schedule = db.query(Schedule).get(schedule_id)
                if schedule:
                    schedule.last_run_at = datetime.utcnow()    
                    db.commit()
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
            blog = db.query(Blog).get(blog_id)
            blog.number_of_articles = len(articles)
            db.commit()
            existing_comparisons = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.user_id == user_id
            ).all()
            # Dictionary that includes the oldest blog_id for each url 
            for comp in existing_comparisons:
                if comp.url not in processed_urls or comp.created_at < processed_urls[comp.url]['created_at']:
                    processed_urls[comp.url] = {
                        'blog_id': comp.blog_id,
                        'created_at': comp.created_at,
                        'short_summary': comp.short_summary
                    }
            # A dictionary for new comparisons and another one for old ones, together with what was the first blog we encountered this url.
            new_comparisons = {url: title for url, title in articles.items() if url not in processed_urls}
            already_processed = {url: {'title': title, 'past_blog_id': processed_urls[url]['blog_id'], 'short_summary': processed_urls[url]['short_summary']} 
                            for url, title in articles.items() if url in processed_urls}

        # Create objects for new and old comparisons, 
        with SessionLocal() as db:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
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
            if new_comparisons:
                for url in new_comparisons.keys():
                    article_text = processor.extract_article_content(url)
                    short_summary = processor.write_small_summary(article_text)
                    extracted_data.append({
                        'url': url,
                        'short_summary': short_summary,
                        'article_text': article_text
                    })
                logging.info(f"Wrote short summaries and extracted article content for {len(new_comparisons)} articles")
                for comp_id, data in zip(new_comparisons_ids, extracted_data):
                    comparison = db.query(BlogProfileComparison).get(comp_id)
                    if not data['short_summary']:
                        comparison.status = BlogProfileComparison.STATUS_FAILED_ON_COMPARISON
                        comparison.error_message = 'Failed to get a short summary for the comparison'
                    else:
                        comparison.short_summary = data['short_summary']
                        comparison.article_text = data['article_text']
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
                        # Check if there are any duplicates
                        if relevance_result:
                            similar_comparisons = db.query(BlogProfileComparison).filter(
                            BlogProfileComparison.user_id == user_id,
                            BlogProfileComparison.status.in_([
                                BlogProfileComparison.STATUS_ACTION_PENDING_TO_DRAFT,
                                BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST,
                                BlogProfileComparison.STATUS_DRAFTING,
                                BlogProfileComparison.STATUS_POSTED_LINKEDIN
                            ]),
                            BlogProfileComparison.created_at >= datetime.utcnow() - timedelta(days=7)
                            ).all()

                            # Create dictionary of recent positive comparisons
                            potential_similar_article_dict = {comp.id: comp.title for comp in similar_comparisons if comp.title}

                            # Check if the current comparison title is similar to any of the recent positive comparisons
                            duplicate_article_id = processor.check_title_similarity(blog_comparison.title, potential_similar_article_dict)

                            if duplicate_article_id != 'No':
                                logging.warning(f"Found duplicate article ID: {duplicate_article_id}")
                                blog_comparison.duplicate_article_id = duplicate_article_id
                                blog_comparison.status = BlogProfileComparison.STATUS_DUPLICATE_ARTICLE
                            else:
                                blog_comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_DRAFT
                                fitting_articles += 1
                        else:
                            blog_comparison.comparison_result = False
                            blog_comparison.status = BlogProfileComparison.STATUS_DEEMED_NOT_RELEVANT
                    except Exception as e:
                        blog_comparison.status = BlogProfileComparison.STATUS_FAILED_ON_COMPARISON
                        blog_comparison.error_message =str(e)
                        blog_comparison.comparison_result = None
                        logging.error(f"Failed to process comparison for URL {blog_comparison.url}: {str(e)}")
                    db.commit()
        
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.COMPLETED
            blog.number_of_fitting_articles = fitting_articles
            db.commit()
            logging.warning(f"Blog analysis completed for blog_id {blog_id}, user_id {user_id} with {fitting_articles} fitting articles")
    except Exception as e:
        logging.error(f"Error in the second step of processing blog {blog_id} for user {user_id}: {str(e)}")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = Blog.FAILED
            blog.error_message = str(e)
            db.commit()
        raise e