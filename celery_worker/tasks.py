from celery_worker.config import celery_app
from app.core.content_processor import SyncAsyncContentProcessor
from app.database.database import SessionLocal
from app.database.models import User, ProcessingResult
from datetime import datetime, timezone
import json

@celery_app.task(bind=True)
def process_url_task(self,url:str,user_id:int,result_id:int):
    db = SessionLocal()
    try:
        try:
            # Call the process url to get the result
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
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

