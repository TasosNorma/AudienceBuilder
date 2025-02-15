from celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.database.database import SessionLocal
from app.database.models import User, ProcessingResult, ProfileComparison, Profile, Blog, BlogProfileComparison
from app.api.general import Blog_Profile_Comparison_Handler
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

# Is called when user pressed "Draft", it creates a new processing result and calls the send_draft to show it to the user.
@celery_app.task(bind=True)
def process_url_for_whatsapp(self,comparison_id:int,user_id:int):
    from app.core.whatsapp import WhatsappHandler
    comparison_handler = Blog_Profile_Comparison_Handler(user_id=user_id)
    db = SessionLocal()
    try:
        logging.info(f"Starting process_url_for_whatsapp task for comparison_id: {comparison_id}")
        comparison_handler.update_comparison_status(comparison_id=comparison_id,new_status="Drafting Post")
        result = comparison_handler.get_comparison_by_id(comparison_id=comparison_id)
        if result["status"] == "error":
            return result
        comparison = result["comparison"]
        url = comparison.url
        if comparison.message_sid:
            message_sid = comparison.message_sid
        else:
            message_sid = None

        user = db.query(User).get(user_id)
        processor = SyncAsyncContentProcessor(user)
        logging.info(f"Processing URL content for comparison {comparison_id}")
        post_result = processor.process_url(url)
        
        logging.info(f"Creating ProcessingResult for comparison {comparison_id}")
        processing_result = ProcessingResult(
            user_id=user_id,
            url=url,
            status="success", 
            tweets=json.dumps(post_result.get("tweets", [])),
            tweet_count=post_result.get("tweet_count", 0),
            message_sid=message_sid,
            whatsapp_triggered=True,
            task_id=self.request.id,
            created_at_utc=datetime.now(timezone.utc),
            blog_comparison_id = comparison_id
        )
        db.add(processing_result)
        db.commit()
        logging.info(f"Created ProcessingResult with id: {processing_result.id}")

        # Get a fresh comparison object from the database in order to update it.
        comparison = db.query(BlogProfileComparison).get(comparison_id)
        comparison.processing_result_id = processing_result.id
        comparison_handler.update_comparison_status(comparison_id=comparison_id,new_status="Drafted Post")
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

# 1. Is called either from Blog_Analysis_Handler.create_blog_analyse_session or directly from the scheduler
# 2. Creates a Blog Analysis, extracts all articles from the blog
# 3. Checks if Articles have been already processed before, if not, it finds out if they are relevant to the user profile
# 4. It then calls the Whatsapp_Handler to notify the user.
@celery_app.task(bind=True)
def blog_analyse(self, url: str, user_id: int, schedule_id: int = None):
    blog_id = None
    logging.info(f"Starting blog analysis task for user {user_id} with URL: {url}")
    try:
        with SessionLocal() as db:
            logging.info(f"Starting Blog_Analysis of URL: {url}")
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            blog = Blog(
                    url=url,
                    user_id=user_id,
                    status="processing", 
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
                    status="processing"
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
                    status="already_processed"
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
                        comparison.status = "failed"
                        comparison.error_message = 'Failed to get a short summary for the comparison'
                    else:
                        comparison.short_summary = short_summary
                db.commit()


            logging.info(f"Identifying if there are any relevant comparisons in blog_analysis {blog_id} and updating the database")
            with SessionLocal() as db:
                user = db.query(User).get(user_id)
                processor = SyncAsyncContentProcessor(user)
                blog_comparisons = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.blog_id == blog_id,
                    BlogProfileComparison.status == "processing"
                ).all()
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
                    except Exception as e:
                        blog_comparison.status = "failed"
                        blog_comparison.comparison_result = None
                        logging.error(f"Failed to process comparison for URL {blog_comparison.url}: {str(e)}")
                    db.commit()
        
        logging.info(f"Updating Blog_Analysis Status and inserting relevant comparison count,there were {fitting_articles} fitting articles")
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = "completed"
            blog.number_of_fitting_articles = fitting_articles
            db.commit()
            if fitting_articles >= 1:
                logging.info("Notifying user via whatsapp for the relevant articles found")
                try:
                    from app.core.whatsapp import WhatsappHandler
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
        with SessionLocal() as db:
            blog = db.query(Blog).get(blog_id)
            blog.status = "failed"
            blog.error_message = str(e)
            db.commit()
        return {
            "status": "error",
            "blog_id": blog_id,
            "message": str(e)
        }
    