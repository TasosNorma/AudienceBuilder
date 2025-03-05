from ..database.database import SessionLocal
from ..database.models import Schedule,User,BlogProfileComparison,Post,Prompt
from ..celery_worker.config import beat_dburi
from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, Period
from sqlalchemy_celery_beat.session import SessionManager
import logging
from datetime import datetime
import json
import os
import requests
from cryptography.fernet import Fernet
import re
from urllib.parse import urlparse

class Schedule_Handler:
    def __init__(self,user_id: int) -> None:
        self.user_id = user_id
        
    def create_blog_schedule(self, url: str,minutes: int):
        app_db = SessionLocal()
        try:
            # Create celery schedule
            session_manager = SessionManager()
            beat_session = session_manager.session_factory(beat_dburi)
            
            interval_schedule = IntervalSchedule(
                every=minutes,
                period=Period.MINUTES
            )
            beat_session.add(interval_schedule)
            beat_session.flush()  # Flush to get the ID

            # MAKE BEAUTIFUL NAME FOR SCHEDULE AUTOMATICALLY.

            # Extract domain and path for a more meaningful name
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            path = parsed_url.path.strip('/')
            # Remove .com, .org, etc. from domain
            domain = re.sub(r'\.[a-z]+$', '', domain)
            # Create a more meaningful task name
            if path:
                task_name = f'{domain.capitalize()}/{path}'
            else:
                task_name = f'{domain.capitalize()}'
            # Fallback to timestamp if we couldn't extract a proper name
            if not task_name:
                task_name = f'blogs{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            
            schedule = Schedule(
            user_id=self.user_id,
            name=task_name,
            url=url,
            minutes=minutes,
            interval_schedule_id=interval_schedule.id
            )
            app_db.add(schedule)
            app_db.flush()
            
            interval_task = PeriodicTask(
                schedule_model=interval_schedule,
                name=task_name,
                task='app.celery_worker.tasks.blog_analyse',
                args=json.dumps([url, self.user_id, schedule.id]),
                kwargs=json.dumps({}),
                description='Scheduled URL processing task'
            )
            beat_session.add(interval_task)
            beat_session.flush()  # Flush to get the ID
            schedule.periodic_task_id = interval_task.id
            
            # Commit both sessions
            beat_session.commit()
            app_db.commit()
        except Exception as e:
            beat_session.rollback()
            app_db.rollback()
            logging.error(f"Error creating scheduled task: {str(e)}")
            raise e
        finally:
            beat_session.close()
            app_db.close()

    def disable_schedule(self,schedule_id:int):
        app_db = SessionLocal()
        session_manager = SessionManager()
        beat_session = session_manager.session_factory(beat_dburi)

        try:
            # Get the schedule from our application database
            schedule = app_db.query(Schedule).filter_by(id=schedule_id,user_id=self.user_id).first()
            if not schedule:
                return {
                    "status": "error",
                    "message": f"Schedule with id {schedule_id} not found or access denied"
                }

            # Disable the periodic task in beat database
            periodic_task = beat_session.query(PeriodicTask).filter_by(id=schedule.periodic_task_id).first()
            if periodic_task:
                periodic_task.enabled = False
            
            # Mark our schedule as inactive
            schedule.is_active = False
            
            # Commit both changes
            beat_session.commit()
            app_db.commit()
        except Exception as e:
            beat_session.rollback()
            app_db.rollback()
            logging.error(f"Error disabling schedule: {str(e)}")
            raise e
        finally:
            beat_session.close()
            app_db.close()
             
class Blog_Profile_Comparison_Handler:    
    @classmethod
    def update_comparison_status(cls, comparison_id: int, new_status: str,user_id:int):
        with SessionLocal() as db:
            try:
                comparison = db.query(BlogProfileComparison).filter(
                    BlogProfileComparison.id == comparison_id,
                    BlogProfileComparison.user_id == user_id
                ).first()
                if not comparison:
                    raise ValueError("Comparison not found or access denied")
                else:
                    comparison.status = new_status
            except Exception as e:
                db.rollback()
                comparison.status = BlogProfileComparison.STATUS_FAILED
                comparison.error_message = str(e)
                logging.error(f"Error updating comparison status: {str(e)}")
                raise e
            db.commit()
    
class Post_Handler:
    @classmethod
    def get_post_in_parts(cls,post_id:int):
        try:
            with SessionLocal() as db:
                parts = []
                post = db.query(Post).get(post_id)
                parts = json.loads(post.parts)
                
                return parts
        except Exception as e:
            logging.error(f"Error getting tweet in parts: {str(e)}")
            raise e

class User_Handler:
    def __init__(self, user_id: int = None):
        self.user_id = user_id

    def set_default_prompt(self,user_id:int):
        with SessionLocal() as db:
            try:
                default_prompt_2 = Prompt(
                    type=Prompt.TYPE_PROFILECOMPARING,
                    name=Prompt.NAME_PROFILECOMPARISONPROMPT,
                    description = 'Compares an article with the profile and returns Yes or No based on Fit.',
                    user_id=user_id,
                    template="""
                You will receive two inputs: a profile description and an article. Your task is to determine if the person described in the profile would find the article relevant, interesting, and suitable for sharing on their social media.
                You must be very strict: only answer "Yes" if the article strongly aligns with their interests, professional focus, or sharing habits as described in the profile. Otherwise, answer "No".

                Instructions:
                1. Read the profile carefully to understand the individual's professional background, interests, and the types of content they are likely to share.
                2. Read the article and assess its topic, tone, and relevance to the profile's interests.
                3. If the article's content clearly matches the individual's interests or sharing criteria described in the profile, respond with "Yes".
                4. If it does not, respond with "No".
                5. Provide no additional commentary—only "Yes" or "No".

                Profile:
                "{profile}"

                Article:
                "{article}"
                """,
                    input_variables='["profile", "article"]',
                    is_active=True
                )
                default_prompt_1 = Prompt(
                    name = Prompt.NAME_LINKEDININFORMATIVEPOSTGENERATOR,
                    type=Prompt.TYPE_POSTGENERATING,
                    description = 'Generates an informative post for LinkedIn',
                    user_id = user_id,
                    template = """
            You are a professional linkedin post writer who is given articles from the web and is tasked to write nice engaging and informative linkedin posts about the contents of the articles. In your draft, you should:

            1. Start with a compelling hook, begin with an attention grabbing yet relevant and smart opening line.
            2. You're just reporting on news so sound very objective and don’t promote anything
                1. Avoid Jargon keep it as professional as possible. 
                2. Don't comment on opinions, focus mainly on facts 
            3. Try to be as simple as possible
            4. Incorporate emojis into your post
            5. Craft compelling headline
            6. Be up to 250 words
            7. Add 5-10 relevant hashtags
            8. Add bullet points to structure the post
            ### Suffix_     

            ** Primary Article **
            This is the article:
            {article}

            """,
                input_variables='["article"]',
                is_active=True
                )
                db.add(default_prompt_2)
                db.add(default_prompt_1)
                db.commit()
            except Exception as e:
                db.rollback()
                logging.error("Error setting default prompts for user %s: %s", user_id, e)
                raise e
    
    def create_new_user(self,email:str,password:str):
        with SessionLocal() as db:
            try:
                user = User(email=email, is_active = True,is_onboarded=False)
                user.set_password(password)
                db.add(user)
                db.commit()
                db.flush()
                self.set_default_prompt(user_id=user.id)
            except Exception as e:
                db.rollback()
                logging.error(f"Error creating the user : {str(e)}")
                raise e
               
class Prompt_Handler:
    def __init__(self,user_id:int = None):
        self.user_id = user_id
    
    @classmethod
    def get_prompt_template(cls,prompt_name: str, user_id: int):
        with SessionLocal() as db:
            try:
                prompt = db.query(Prompt).filter(
                    Prompt.name == prompt_name, 
                    Prompt.user_id == user_id
                ).first()
                if prompt:
                    return prompt.template
                else:
                    raise ValueError(f"No prompt found for type {prompt_name} and user {user_id}")
            except Exception as e:
                raise e
        
class LinkedIn_Auth_Handler:
    def __init__(self) -> None:
        self.client_id = os.environ.get('LINKEDIN_CLIENT_ID')
        self.client_secret = os.environ.get('LINKEDIN_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('LINKEDIN_CALLBACK_URL')
        self.fernet = Fernet(os.environ.get('ENCRYPTION_KEY').encode())

    def handle_callback(self, code, user_id):
        try:
            # Exchange the authorization code for an access token
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            payload = {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri
            }
            response = requests.post(token_url, data=payload)
            if response.status_code != 200:
                logging.error(f"LinkedIn token exchange failed: {response.text}")
                return False
            
            token_data = response.json()
            # Store the tokens in the database
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                user.linkedin_access_token = self.fernet.encrypt(token_data['access_token'].encode()).decode()
                user.linkedin_access_token_expires_in = token_data['expires_in']
                user.linkedin_refresh_token = self.fernet.encrypt(token_data.get('refresh_token', 'Not included in response').encode()).decode()
                user.linkedin_refresh_token_expires_in = token_data.get('refresh_token_expires_in', 0)
                user.linkedin_scope = token_data['scope']
                user.linkedin_connected = True
                db.commit()
        except Exception as e:
            raise e
        
class LinkedIn_Client_Handler:
    def __init__(self, user_id :int) -> None:
        try:
            self.user_id = user_id
            self.fernet = Fernet(os.environ.get('ENCRYPTION_KEY').encode())
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.linkedin_connected or not user.linkedin_access_token:
                    raise ValueError("User not connected to LinkedIn or missing access token")
                self.access_token = self.fernet.decrypt(user.linkedin_access_token.encode()).decode()
            self.headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0',
                'LinkedIn-Version':'202502'
            }
            self.profile = self.get_profile()
        except Exception as e:
            raise e
    

    def get_profile(self):
        try:
            url = "https://api.linkedin.com/v2/userinfo"
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                logging.error(f"Failed to get LinkedIn profile: {response.status_code} {response.text}")
                raise Exception(f"LinkedIn API error: {response.status_code}")
            profile_data = response.json()
            return profile_data
        except Exception as e:
            logging.error(f"Error getting LinkedIn profile: {str(e)}")
            raise e

    def post (self, text:str):
        try:
            profile_id = self.profile.get('sub')
            person_urn = f"urn:li:person:{profile_id}"
            post_url = "https://api.linkedin.com/rest/posts"
            
            payload = {
                "author": person_urn,
                "commentary": text,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": []
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False
            }
            response = requests.post(post_url, headers=self.headers, json=payload)
            if response.status_code not in [200, 201]:
                logging.error(f"Failed to post to LinkedIn: {response.status_code} {response.text}")
                raise Exception(f"LinkedIn API error: {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error posting to LinkedIn: {str(e)}")
            raise e
        
# if __name__ == "__main__":
#     try:
#         # Example usage
#         linkedin = LinkedIn_Client_Handler(26) 
#         linkedin.post("Test post from LinkedIn API integration")
#         print("Successfully posted to LinkedIn")
#     except Exception as e:
#         print(f"Failed to post: {str(e)}")


