from twilio.rest import Client
import os
import logging
from dotenv import load_dotenv 
from ..database.models import BlogProfileComparison,User,ProcessingResult
from ..database.database import SessionLocal
import json
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# This class is used to handle responses only
class ResponseHandler:
    def __init__(self) -> None:
        load_dotenv()
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')    
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Missing required Twilio environment variables")
        self.client = Client(self.account_sid, self.auth_token)
    
    # Gets triggered by webhooks, handles all responses coming from webhooks and performs relevant actions.
    def handle_response(self, original_message_sid: str, response: str, message_sid: str = None) -> bool:
        db = SessionLocal()
        try:
            
            if response == "ignore":
                try:
                    comparison = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.message_sid == original_message_sid
                    ).first()
                    comparison.whatsapp_status = "Ignored Article"
                    db.commit()
                    logging.info(f"Marked comparison {comparison.id} as ignored")
                    return True
                except Exception as e:
                    comparison = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.message_sid == original_message_sid
                    ).first()
                    comparison.whatsapp_status = "Failed"
                    comparison.error_message = f"Error occured receiving the ignore response : {str(e)}"
                    logging.error(f"Error occured receiving the ignore response : {str(e)}")
                    db.commit()
                    return False
            
            elif response == "draft":
                try:
                    comparison = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.message_sid == original_message_sid
                    ).first()
                    comparison.whatsapp_status = "Drafted Post"
                    # Import here to avoid circular import
                    from celery_worker.tasks import process_url_for_whatsapp
                    task = process_url_for_whatsapp.delay(comparison.id)
                    logging.info(f"Queued process_url_for_whatsapp task for comparison {comparison.id} the task is {task.id}")
                    db.commit()
                    return True
                except Exception as e:
                    comparison = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.message_sid == original_message_sid
                    ).first()
                    comparison.whatsapp_status = "Failed"
                    comparison.error_message = f"Error occurred while processing draft response: {str(e)}"
                    logging.error(f"Error occurred while processing draft response: {str(e)}")
                    db.commit()
                    return False
            
            elif response == "post":
                try:
                    processing_result = db.query(ProcessingResult).filter(
                        ProcessingResult.message_sid == original_message_sid
                    ).first()
                    if processing_result is None:
                        raise ValueError(f"No processing result found for message_sid: {original_message_sid}")
                    processing_result.posted = True
                    comparison = db.query(BlogProfileComparison).filter(
                        BlogProfileComparison.id == processing_result.blog_comparison_id
                    ).first()
                    comparison.whatsapp_status = "Posted"
                    db.commit()
                    logging.info(f"Comparison with ID: {comparison.id} has been marked as Whatsapp_Status = Posted")
                    logging.info(f"Processing result with ID {processing_result.id} has been marked as Posted = True ")
                    return True
                except Exception as e:
                    comparison = db.query(BlogProfileComparison).filter(
                        BlogProfileComparison.id == processing_result.blog_comparison_id if processing_result else None
                    ).first()
                    if comparison:
                        comparison.whatsapp_status = "Failed"
                        comparison.error_message = f"Error occurred while processing post response: {str(e)}"
                        db.commit()
                    logging.error(f"Error occurred while processing post response: {str(e)}")
                    return False

                
            
            elif response == "ignore draft":
                try:
                    processing_result = db.query(ProcessingResult).filter(
                        ProcessingResult.message_sid == original_message_sid
                    ).first()
                    if processing_result is None:
                        raise ValueError(f"No processing result found for message_sid: {original_message_sid}")
                    processing_result.posted = False
                    comparison = db.query(BlogProfileComparison).filter(
                        BlogProfileComparison.id == processing_result.blog_comparison_id
                    ).first()
                    comparison.whatsapp_status = "Ignored Draft"
                    db.commit()
                    logging.info(f"Processing result was marked as ignored")
                    return True
                except Exception as e:
                    processing_result = db.query(ProcessingResult).filter(
                        ProcessingResult.message_sid == original_message_sid
                    ).first()
                    comparison = db.query(BlogProfileComparison).filter(
                        BlogProfileComparison.id == processing_result.blog_comparison_id if processing_result else None
                    ).first()
                    if comparison:
                        comparison.whatsapp_status = "Failed"
                        comparison.error_message = f"Error occurred while processing ignore draft response: {str(e)}"
                        db.commit()
                    logging.error(f"Error occurred while processing ignore draft response: {str(e)}")
                    return False
                
        except Exception as e:
            logging.error(f"Error handling whatsapp response: {str(e)}")
            return False
        finally:
            db.close()