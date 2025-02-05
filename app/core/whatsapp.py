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

#This class is used to send messages only
class WhatsappHandler:
    def __init__(self) -> None:
        load_dotenv()
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')    
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Missing required Twilio environment variables")
        self.client = Client(self.account_sid, self.auth_token)

    # Send a relevant article to user expects response of (Draft) or (Ignore)
    def send_notify_sms(self, to_number: str, article_data: dict) -> bool:
        try:
            message = self.client.messages.create(
                from_='whatsapp:' + self.from_number,
                to='whatsapp:' + to_number,
                content_sid='HX70e6a172c78c5d72cbf2d6f68f8a0239', 
                content_variables=json.dumps({
                    '1': article_data['summary'],
                    '2': article_data['url']
                })
            )
            logging.info(f"The content of the message {message.body}")
            logging.info(f"Successfully sent whatsapp message using template. Message SID: {message.sid}")
            return True, message.sid
        except Exception as e:
            logging.error(f"Failed to send whatsapp message: {str(e)}")
            return False
    
    # Searches for relevant articles and gives them all to send_notify_sms
    def notify_relevant_articles(self, user_id: int, blog_id: int) -> bool:
        db = SessionLocal()
        logging.info(f"Starting notification process for user_id: {user_id}, blog_id: {blog_id}")
        try:
            user = db.query(User).get(user_id)
            if not user:
                logging.error(f"User with id {user_id} not found")
                return False
            logging.info(f"Found user with phone no: {user.phone_number}")
            relevant_articles = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.blog_id == blog_id,
                BlogProfileComparison.user_id == user_id,
                BlogProfileComparison.comparison_result == "relevant"
            ).all()
            logging.info(f"Found {len(relevant_articles)} relevant articles")
            logging.info(f"Starting the processing of the articles to send messages in whatsapp")
            
            # Send notification for each relevant article
            for article in relevant_articles:
                article_data = {
                    'summary': article.short_summary[:100] + "...",
                    'url': article.url
                }
                article.whatsapp_status = "Notified User"
                success, message_sid = self.send_notify_sms(user.phone_number, article_data)
                if success:
                    logging.info(f"Relevant article found, sms is sent. The id of the article_comparison is :{article.id}")
                    article.message_sid = message_sid
                    db.commit()
        except Exception as e:
            logging.error(f"Error sending notifications: {str(e)}")
            return False
        finally:
            db.close()
            return True
        
    # Gets trigered by the process_url_for_whatsapp task and sends the draft to the user to approve
    def send_draft(self,processing_result_id:int) -> bool:
        db = SessionLocal()
        try:
            # Get the processing result
            result = db.query(ProcessingResult).get(processing_result_id)
            if not result:
                logging.error(f"Processing result with id {processing_result_id} not found")
                return False
            
            user = db.query(User).get(result.user_id)
            tweets = json.loads(result.tweets)
            thread_title = tweets[0].strip('*')

            # Get the base URL from environment variable
            base_url = os.getenv('BASE_URL', 'http://localhost:10000')
            result_url = f"{base_url}/processing_result/{result.id}"
            logging.info(f"Draft thread title: {thread_title}")
            logging.info(f"Url: {result_url}")
            
            draft_data = {
                "1": thread_title,
                "2": result_url
            }

            message = self.client.messages.create(
            from_='whatsapp:' + self.from_number,
            to='whatsapp:' + user.phone_number,
            content_sid='HX22190b1d82fe9da1a786728f9a0a3d59',  
            content_variables=json.dumps(draft_data)
            )
            result.message_sid = message.sid
            db.commit()
            logging.info(f"Successfully sent draft message. Message SID: {message.sid}")
            return True
        except Exception as e:
            logging.error(f"Error sending draft: {str(e)}")
            return False
        finally:
            db.close()


if __name__ == "__main__":
    whatsapp = WhatsappHandler()
    try:
        success = whatsapp.notify_relevant_articles(14,27)
        print(f"Notification process completed. Success: {success}")
    except Exception as e:
        print(f"Error sending notifications: {str(e)}")



