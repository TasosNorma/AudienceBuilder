from app.database.database import SessionLocal
from app.database.models import User, Post
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