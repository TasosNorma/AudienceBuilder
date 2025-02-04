from celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.database.database import SessionLocal
from app.database.models import User, ProcessingResult, ProfileComparison, Profile, Blog, BlogProfileComparison
from datetime import datetime, timezone
import json
import asyncio
import logging



@celery_app.task(bind=True)
def process_url_task(self,url:str,user_id:int,result_id:int):
    db = SessionLocal()
    try:
        try:
            # Call the process url to get the result
            user = db.query(User).get(user_id)
            print(f"Got user with id f{user.id}")
            processor = SyncAsyncContentProcessor(user)
            print(f"Successfully Initiated the SyncAsyncContent Processor")
            result = processor.process_url(url)
            # Find the processing result and add all the relevant info
            processing_result = db.query(ProcessingResult).get(result_id)
            processing_result.status = result["status"]
            processing_result.tweets = json.dumps(result.get("tweets", []))
            processing_result.tweet_count = result.get("tweet_count", 0)
            processing_result.error_message = result.get("message", None)
            db.add(processing_result)
            db.commit()
        except Exception as e:
            print(f"Error in either processing the url or inserting new result in the database {str(e)}")
            processing_result.status = "failed"
            processing_result.error_message = str(e)
            db.commit()
            return {
                "status": "Failure of processing task",
                "task_id": self.request.id,
                "result_id": processing_result.id
            }
            raise
        
        return {
            "status": "success",
            "task_id": self.request.id,
            "result_id": processing_result.id
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@celery_app.task(bind=True)
def process_url_task_no_processing_id(self,url:str,user_id:int):
    db = SessionLocal()

    try:
        user = db.query(User).get(user_id)
        processor = SyncAsyncContentProcessor(user)
        result = processor.process_url(url)
        processing_result = ProcessingResult(
                user_id=user_id,
                url=url,
                status=result["status"],
                created_at_utc=datetime.now(timezone.utc),
                tweets = json.dumps(result.get("tweets", [])),
                error_message = result.get("message", None),
                tweet_count = result.get("tweet_count", 0)
            )
        db.add(processing_result)
        db.commit()
        return {
            "status": "Success",
            "result_id": processing_result.id,
            "task_id": self.request.id
        }
    except Exception as e:
        print(f"Error in either processing the url or inserting new result in the database {str(e)}")
        processing_result.status = "failed"
        processing_result.error_message = str(e)
        db.commit()
        return {
            "status": "Failure",
            "result_id": processing_result.id,
            "task_id": self.request.id
        }
    finally:
        db.close()

@celery_app.task(bind=True)
def compare_profile_task(self, comparison_id: int, user_id: int):
    db = SessionLocal()
    try:
        # Get the comparison record
        logging.info("Trying to get the comparison...")
        comparison = db.query(ProfileComparison).get(comparison_id)
        if not comparison:
            raise ValueError(f"Profile comparison {comparison_id} not found")
        
        # Get the user
        logging.info("Trying to get the user...")
        user = db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get the profile
        logging.info("Trying to get the profile...")
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        if not profile:
            raise ValueError(f"Profile for user {user_id} not found")
        
        # Store the current profile interests
        logging.info("Trying to get the interest descriptions...")
        comparison.profile_interests = profile.interests_description
        
        # Create processor and get article summary
        logging.info("Trying to initialise the processor...")
        processor = SyncAsyncContentProcessor(user)
        logging.info(f"Created processor: {processor}")
        logging.info(f"Processor crawler: {processor.crawler}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logging.info("Attempting to get article summary...")
            summary = loop.run_until_complete(processor.crawler.write_small_summary(comparison.url))
            comparison.short_summary = summary
        finally:
            loop.close()

        # Get comparison result
        logging.info("Attempting to check article relevance...")
        is_relevant = processor.is_article_relevant(comparison.url)
        logging.info(f"Article relevance result: {is_relevant}")

        # Update the comparison record
        comparison.status = "completed"
        comparison.comparison_result = "relevant" if is_relevant else "not_relevant"

        db.commit()
        logging.info(f"Successfully completed profile comparison {comparison_id} for user {user_id} with result: {comparison.comparison_result}")
        return {
            "status": "success",
            "comparison_id": comparison_id,
            "result": comparison.comparison_result
        }
    except Exception as e:
        logging.error(f"Error processing profile comparison {comparison_id} for user {user_id}: {str(e)}")
        db.rollback()
        comparison.status = "failed"
        comparison.comparison_result = f"Error: {str(e)}"
        db.commit()
        return {
            "status": "error",
            "comparison_id": comparison_id,
            "message": str(e)
        }
    finally:
        db.close()

# This function:
# 1. Takes a blog_id and user_id as input
# 2. Extracts all articles from the blog's URL
# 3. Creates pending BlogProfileComparison entries in the database for each article
# 4. Generates a short summary for each article
# 5. Compares each summary against the user's profile interests
# 6. Updates the comparison records as either "relevant" or "not relevant"
@celery_app.task(bind=True)
def blog_analyse_task(self, blog_id: int, user_id: int):

    # Get the blog and the user, get all the relevant articles of the blog, create database records for each one,
    # Then get a small summary for each one and update the records in the database. 
    try:
        db = SessionLocal()
        logging.info(f"Starting the first step of the blog analysis of blog_id: {blog_id}, user_id: {user_id}")
        # Get the blog record, the user and initiate the processor.
        blog = db.query(Blog).get(blog_id)
        if not blog:
            raise ValueError(f"Blog with id {blog_id} not found")
        user = db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        processor = SyncAsyncContentProcessor(user)

        # Get all articles from the blog
        logging.info(f"Extracting articles from blog URL: {blog.url}")
        try:
            # Create and use an event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                articles = loop.run_until_complete(processor.crawler.extract_all_articles_from_page(blog.url))
                logging.info(f"Found {len(articles)} articles in blog")
            finally:
                loop.close()
        except Exception as e:
            logging.error(f"Failed to extract articles from blog: {str(e)}")
            raise

        # Update blog with number of articles found
        blog.number_of_articles = len(articles)
        blog.status = "processing"
        db.commit()

        # Get user's profile for comparison and create all the BlogProfileEntries records and commit them to the database.
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        if not profile:
            raise ValueError(f"Profile for user {user_id} not found")
        logging.info("Creating BlogProfileComparison entries")
        comparisons = []
        for url, title in articles.items():
            comparison = BlogProfileComparison(
                url=url,
                blog_id=blog_id,
                user_id=user_id,
                profile_interests=profile.interests_description,
                status="processing"
            )
            db.add(comparison)
            comparisons.append(comparison)
        db.commit()
        logging.info("Created BlogProfileComparison entries and now trying to write all the small summaries")

        # Make a small summary for each article and put it inside a list
        short_summaries = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for url in articles.keys():
                short_summary = loop.run_until_complete(processor.crawler.write_small_summary(url))
                short_summaries.append(short_summary)
        finally:
            loop.close()

        # Update each comparison with its corresponding small summary
        logging.info("Updating comparisons with small summaries")
        try:
            for comparison, short_summary in zip(comparisons, short_summaries):
                if not short_summary:
                    comparison.status = "failed"
                else:
                    comparison.short_summary = short_summary
            db.commit()
        except Exception as e:
            logging.error(f"Failed to update comparisons with summaries: {str(e)}")
            raise
    except Exception as e:
        logging.error(f"Error in the first step of processing blog {blog_id} for user {user_id}: {str(e)}")
        blog.status = "failed"
        blog.error_message = str(e)
        db.commit()
        return {
            "status": "error",
            "blog_id": blog_id,
            "message": str(e)
        }
    finally:
        db.close()

    # Get the blog comparison records from the database, compare them to the profile and update the database records of 
    # Both comparison results and the blog status. 
    try:
        db = SessionLocal()
        logging.info(f"Starting async blog analysis for blog_id: {blog_id}, user_id: {user_id}")
        # Get the blog record, the user and initiate the processor.
        blog = db.query(Blog).get(blog_id)
        if not blog:
            raise ValueError(f"Blog with id {blog_id} not found")
        user = db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        processor = SyncAsyncContentProcessor(user)
        # Get all BlogProfileComparison records for this user and blog
        blog_comparisons = db.query(BlogProfileComparison).filter(
            BlogProfileComparison.user_id == user_id,
            BlogProfileComparison.blog_id == blog_id
        ).all()
        
        fitting_articles = 0
        for blog_comparison in blog_comparisons:
            try:
                short_summary = blog_comparison.short_summary
                relevance_result = processor.is_article_relevant_short_summary(short_summary)
                blog_comparison.comparison_result = "relevant" if relevance_result else "not_relevant"
                blog_comparison.status = "completed"
                if relevance_result:
                    fitting_articles += 1
                db.commit()
            except Exception as e:
                blog_comparison.status = "failed"
                blog_comparison.comparison_result = None
                db.commit()
                logging.error(f"Failed to process comparison for URL {blog_comparison.url}: {str(e)}")

        # Update blog status and fitting articles count
        blog.status = "completed"
        blog.number_of_fitting_articles = fitting_articles
        db.commit()

        return {
            "status": "success",
            "blog_id": blog_id,
            "fitting_articles": fitting_articles
        }
    except Exception as e:
        logging.error(f"Error in the second step of processing blog {blog_id} for user {user_id}: {str(e)}")
        blog.status = "failed"
        blog.error_message = str(e)
        db.commit()
        return {
            "status": "error",
            "blog_id": blog_id,
            "message": str(e)
        }
    finally:
        db.close()


# This function:
# 1. Takes a blog_id and user_id as input
# 2. Extracts all articles from the blog's URL
# 3. Creates pending BlogProfileComparison entries in the database for each article
# 4. If the article has already been processed for that user, the database entry will reflect that.
# 5. Generates a short summary for new article
# 6. Compares each summary against the user's profile interests
# 7. Updates the comparison records as either "relevant" or "not relevant"               
@celery_app.task(bind=True)
def blog_analyse_task_filter_out_past(self, blog_id: int, user_id: int):

    # Get the blog and the user, get all the relevant articles of the blog, create database records for each one,
    # Then get a small summary for each one and update the records in the database. 
    try:
        db = SessionLocal()
        logging.info(f"Starting the first step of the blog analysis of blog_id: {blog_id}, user_id: {user_id}")
        # Get the blog record, the user and initiate the processor.
        blog = db.query(Blog).get(blog_id)
        if not blog:
            raise ValueError(f"Blog with id {blog_id} not found")
        user = db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        processor = SyncAsyncContentProcessor(user)
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        if not profile:
            raise ValueError(f"Profile for user {user_id} not found")

        # Get all articles from the blog
        logging.info(f"Extracting articles from blog URL: {blog.url}")
        try:
            # Create and use an event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                articles = loop.run_until_complete(processor.crawler.extract_all_articles_from_page(blog.url))
                logging.info(f"Found {len(articles)} articles in blog")
            finally:
                loop.close()
        except Exception as e:
            logging.error(f"Failed to extract articles from blog: {str(e)}")
            raise

        # Update blog with number of articles found
        blog.number_of_articles = len(articles)
        blog.status = "processing"
        db.commit()

        # After getting articles, check which ones have been processed before
        existing_comparisons = db.query(BlogProfileComparison).filter(
            BlogProfileComparison.user_id == user_id
        ).all()

        # Create a set of already processed URLs
        processed_urls = {comp.url for comp in existing_comparisons}

        # Split articles into new and already processed
        new_articles = {url: title for url, title in articles.items() if url not in processed_urls}
        already_processed = {url: title for url, title in articles.items() if url in processed_urls}
        logging.info(f"Found {len(new_articles)} new articles and {len(already_processed)} already processed articles")

        # Create a list of new comparisons and add the already processed in the database.
        comparisons = []
        for url, title in new_articles.items():
            comparison = BlogProfileComparison(
                url=url,
                blog_id=blog_id,
                user_id=user_id,
                profile_interests=profile.interests_description,
                status="processing"
            )
            db.add(comparison)
            comparisons.append(comparison)

        # Mark already processed articles
        for url in already_processed:
            comparison = BlogProfileComparison(
                url=url,
                blog_id=blog_id,
                user_id=user_id,
                profile_interests=profile.interests_description,
                status="already_processed"
            )
            db.add(comparison)
        db.commit()



        # Get user's profile for comparison and create all the BlogProfileEntries records and commit them to the database.
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        if not profile:
            raise ValueError(f"Profile for user {user_id} not found")
        logging.info("Creating BlogProfileComparison entries")
        
        
        # Make a small summary for each article and put it inside a list
        short_summaries = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for url in new_articles.keys():
                short_summary = loop.run_until_complete(processor.crawler.write_small_summary(url))
                short_summaries.append(short_summary)
        finally:
            loop.close()

        # Update each comparison with its corresponding small summary
        logging.info("Updating comparisons with small summaries")
        try:
            for comparison, short_summary in zip(comparisons, short_summaries):
                if not short_summary:
                    comparison.status = "failed"
                else:
                    comparison.short_summary = short_summary
            db.commit()
        except Exception as e:
            logging.error(f"Failed to update comparisons with summaries: {str(e)}")
            raise
    except Exception as e:
        logging.error(f"Error in the first step of processing blog {blog_id} for user {user_id}: {str(e)}")
        blog.status = "failed"
        blog.error_message = str(e)
        db.commit()
        return {
            "status": "error",
            "blog_id": blog_id,
            "message": str(e)
        }
    finally:
        db.close()

    # Get the blog comparison records from the database, compare them to the profile and update the database records of 
    # Both comparison results and the blog status. 
    try:
        db = SessionLocal()
        logging.info(f"Starting async blog analysis for blog_id: {blog_id}, user_id: {user_id}")
        # Get the blog record, the user and initiate the processor.
        blog = db.query(Blog).get(blog_id)
        if not blog:
            raise ValueError(f"Blog with id {blog_id} not found")
        user = db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        processor = SyncAsyncContentProcessor(user)
        # Get all BlogProfileComparison records for this user and blog
        blog_comparisons = db.query(BlogProfileComparison).filter(
            BlogProfileComparison.user_id == user_id,
            BlogProfileComparison.blog_id == blog_id
        ).all()
        
        fitting_articles = 0
        for blog_comparison in blog_comparisons:
            try:
                short_summary = blog_comparison.short_summary
                if not short_summary:
                    continue
                relevance_result = processor.is_article_relevant_short_summary(short_summary)
                blog_comparison.comparison_result = "relevant" if relevance_result else "not_relevant"
                blog_comparison.status = "completed"
                if relevance_result:
                    fitting_articles += 1
                db.commit()
            except Exception as e:
                blog_comparison.status = "failed"
                blog_comparison.comparison_result = None
                db.commit()
                logging.error(f"Failed to process comparison for URL {blog_comparison.url}: {str(e)}")

        # Update blog status and fitting articles count
        blog.status = "completed"
        blog.number_of_fitting_articles = fitting_articles
        db.commit()

        try:
            if blog.status == "completed":
                whatsapp = WhatsappHandler()
                whatsapp.notify_relevant_articles(user_id,blog_id)
        except Exception as e:
            logging.error(f"Failed to send WhatsApp notifications: {str(e)}")

        return {
            "status": "success",
            "blog_id": blog_id,
            "fitting_articles": fitting_articles
        }
    except Exception as e:
        logging.error(f"Error in the second step of processing blog {blog_id} for user {user_id}: {str(e)}")
        blog.status = "failed"
        blog.error_message = str(e)
        db.commit()
        return {
            "status": "error",
            "blog_id": blog_id,
            "message": str(e)
        }
    finally:
        db.close()


# Is called when user pressed "Draft", it creates a new processing result and calls the send_draft to show it to the user.
@celery_app.task(bind=True)
def process_url_for_whatsapp(self,comparison_id:int):
    from app.core.whatsapp import WhatsappHandler
    db = SessionLocal()
    try:
        logging.info(f"Starting process_url_for_whatsapp task for comparison_id: {comparison_id}")
        comparison = db.query(BlogProfileComparison).get(comparison_id)
        user_id = comparison.user_id
        url = comparison.url
        message_sid = comparison.message_sid
        logging.info(f"Retrieved comparison data - user_id: {user_id}, url: {url}")

        user = db.query(User).get(user_id)
        processor = SyncAsyncContentProcessor(user)
        logging.info(f"Processing URL content for comparison {comparison_id}")
        result = processor.process_url(url)
        
        logging.info(f"Creating ProcessingResult for comparison {comparison_id}")
        processing_result = ProcessingResult(
            user_id=user_id,
            url=url,
            status="success", 
            tweets=json.dumps(result.get("tweets", [])),
            tweet_count=result.get("tweet_count", 0),
            message_sid=message_sid,
            whatsapp_triggered=True,
            task_id=self.request.id,
            created_at_utc=datetime.now(timezone.utc),
            original_blog_comparison = comparison_id
        )
        db.add(processing_result)
        db.commit()
        logging.info(f"Created ProcessingResult with id: {processing_result.id}")

        comparison.processing_result_id = processing_result.id
        db.commit()
        logging.info(f"Updated comparison {comparison_id} with processing_result_id")

        if processing_result:
            logging.info(f"Sending draft via WhatsApp for processing_result: {processing_result.id}")
            whatsapp = WhatsappHandler()
            whatsapp.send_draft(processing_result.id)

        return {
            "status": "success",
            "result_id": processing_result.id,
            "task_id": self.request.id
        }
    except Exception as e:
        logging.error(f"Error processing comparison {comparison_id} for WhatsApp: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        db.close()





