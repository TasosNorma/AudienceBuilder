from app.database.database import SessionLocal
from app.database.models import User, Post, BlogProfileComparison
from app.core.content_processor import SyncAsyncContentProcessor
from datetime import datetime, timezone
import logging

def draft_draft(url: str, prompt_id: int, user_id: int):
    """
    Takes a url, prompt_id and user_id.
    Creates a draft with markdown, plain text and thread list text.
    Default model is gpt-4o.
    """
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
            
            post.markdown_text = processor.draft(url=url, prompt_id=prompt_id)
            post.plain_text = processor.convert_markdown_to_plain_text(post.markdown_text)
            post.thread_list_text = processor.convert_markdown_to_tweet_thread(post.markdown_text)
            post.status = Post.GENERATED
            db.commit()
    except Exception as e:
        logging.error(f"Error drafting draft: {str(e)}")
        with SessionLocal() as db:
            if post_id:
                post = db.query(Post).get(post_id)
                if post:
                    post.status = Post.FAILED
                    post.error_message = str(e)
                    db.commit()
        raise e
    

def draft_action(user_id:int, action_id:int, prompt_id:int):
    """
    Takes a user_id, action_id and prompt_id.
    Creates a draft with markdown, plain text and thread list text.
    Default model is gpt-4o.
    """
    post_id = None
    try: 
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(action_id)
            comparison.status = BlogProfileComparison.STATUS_DRAFTING
            url = comparison.url
            user = db.query(User).get(user_id)
            post = Post(
                user_id=user_id,
                url=url,
                status=Post.PROCESSING,
                created_at_utc=datetime.now(timezone.utc),
                blog_comparison_id = action_id
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
            comparison = db.query(BlogProfileComparison).get(action_id)
            comparison.post_id = post.id
            comparison.status = BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST
            db.commit()
    except Exception as e:
        logging.error(f"Error processing comparison {action_id}  : {str(e)}")
        with SessionLocal() as db:
            post = db.query(Post).get(post_id)
            post.status = Post.FAILED
            post.error_message = str(e)
            comparison = db.query(BlogProfileComparison).get(action_id)
            comparison.status = BlogProfileComparison.STATUS_FAILED_ON_DRAFT
            comparison.error_message = str(e)
            db.commit()
        raise e
    

def draft_group(group_id:int, prompt_id:int, user_id:int):
    post_id = None
    try:
        with SessionLocal() as db:
            post = Post(
                user_id=user_id,
                status=Post.PROCESSING,
                created_at_utc=datetime.now(timezone.utc),
                group_id=group_id
            )
            db.add(post)
            db.commit()
            db.flush()
            post_id = post.id
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            post.markdown_text = processor.draft(group_id=group_id,prompt_id=prompt_id)
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
        logging.error(f"Error drafting group: {str(e)}")
        raise e