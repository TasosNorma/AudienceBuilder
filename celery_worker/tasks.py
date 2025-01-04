from celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.database.database import SessionLocal
from app.database.models import User, ProcessingResult
from datetime import datetime, timezone
import json

@celery_app.task(bind=True)
def process_url_task(self,url:str,user_id:int):
    db = SessionLocal()
    # Enter an entry to the database
    processing_result = ProcessingResult(
        user_id=user_id,
        url=url,
        status="pending",
        task_id=self.request.id,
        created_at_utc=datetime.now(timezone.utc)
    )
    db.add(processing_result)
    db.commit()


    try:
        try:
            try:
                user = db.query(User).get(user_id)
                processor = SyncAsyncContentProcessor(user)
                result = processor.process_url(url)
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                raise

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

