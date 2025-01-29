from twilio.rest import Client
import os
import logging
from dotenv import load_dotenv 
from ..database.models import BlogProfileComparison,User
from ..database.database import SessionLocal


class WhatsappHandler:
    def __init__(self) -> None:
        load_dotenv()
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')    
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Missing required Twilio environment variables")
        self.client = Client(self.account_sid, self.auth_token)

    def send_sms(self, to_number: str, message: str) -> bool:
        try:
            message = self.client.messages.create(
                body=message,
                from_='whatsapp:' + self.from_number,
                to='whatsapp:' + to_number
            )
            logging.info(f"Successfully sent whatsapp message. Message body: {message.body}")
            return True
        except Exception as e:
            logging.error(f"Failed to send whatsapp message: {str(e)}")
            return False
    
    def notify_relevant_articles(self,user_id:int,blog_id:int) -> bool:
        db=SessionLocal()
        try:
            user = db.query(User).get(user_id)
            relevant_articles = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.blog_id == blog_id,
                BlogProfileComparison.user_id == user_id,
                BlogProfileComparison.comparison_result == "relevant"
            ).all()
            # Send notification for each relevant article
            for article in relevant_articles:
                message = f"New relevant article found!\n\nSummary: {article.short_summary[:100]}...\n\nRead more: {article.url}"
                self.send_sms(user.phone_number, message)
        except Exception as e:
            logging.error(f"Error sending notifications: {str(e)}")
        finally:
            db.close()
        


        


if __name__ == "__main__":
    whatsapp = WhatsappHandler()
    test_number = "+306982267633"
    test_message = "Hello! This is a test message from WhatsApp API"
    result = whatsapp.notify_relevant_articles(14,28)



