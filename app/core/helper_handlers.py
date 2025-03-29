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
from urllib.parse import urlparse, parse_qsl
from requests_oauthlib import OAuth1Session
from app.core.default_prompts import DEFAULT_PROMPTS

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
            
            # Create unique periodic task name with user ID and timestamp
            periodic_task_name = f'blog_analyse_user_{self.user_id}_{task_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            interval_task = PeriodicTask(
                schedule_model=interval_schedule,
                name=periodic_task_name,
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

    def set_default_prompts(self, user_id: int):
        with SessionLocal() as db:
            try:
                # Add all default prompts from the imported list
                for prompt_data in DEFAULT_PROMPTS:
                    prompt = Prompt(
                        name=prompt_data["name"],
                        type=prompt_data["type"],
                        description=prompt_data["description"],
                        user_id=user_id,
                        template=prompt_data["template"],
                        input_variables=json.dumps(prompt_data["input_variables"]),
                        is_active=prompt_data["is_active"],
                        system_prompt=prompt_data["system_prompt"],
                        deep_research_prompt=prompt_data["deep_research_prompt"]
                    )
                    db.add(prompt)
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
                self.set_default_prompts(user_id=user.id)
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
        
class Perplexity_Handler:
    def __init__(self) -> None:
        self.api_key = os.environ.get('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY environment variable is not set")
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def deep_research(self, prompt: str) -> str:
        try:
            payload = {
                "model": "sonar-deep-research", 
                "messages": [
                    {"role": "system", "content": "Provide detailed and well-researched responses."},
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logging.error(f"Perplexity API error: {response.status_code} {response.text}")
                raise Exception(f"Perplexity API error: {response.status_code}")
                
            result = response.json()
            content = result["choices"][0]["message"]["content"]
        
            # Remove <think> tags and their contents
            cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            # Remove any remaining thinking tags if they appear separately
            cleaned_content = re.sub(r'</?think>', '', cleaned_content)
            # Trim any extra whitespace that might result from the removal
            cleaned_content = cleaned_content.strip()
            
            return cleaned_content
            
        except Exception as e:
            logging.error(f"Error in Perplexity deep research: {str(e)}")
            raise e

class X_Auth_Handler:
    def __init__(self) -> None:
        self.client_id = os.environ.get('X_CLIENT_ID')
        self.client_secret = os.environ.get('X_CLIENT_SECRET')
        self.callback_url = os.environ.get('X_CALLBACK_URL')
        self.fernet = Fernet(os.environ.get('ENCRYPTION_KEY').encode())
        
    def get_request_token(self):
        """
        Step 1: Get a request token from X
        """
        try:
            # Create OAuth1 session
            oauth = OAuth1Session(
                client_key=os.environ.get('X_API_KEY'),
                client_secret=os.environ.get('X_KEY_SECRET')
            )
            
            # Get request token
            request_token_url = "https://api.x.com/oauth/request_token"
            params = {"oauth_callback": self.callback_url}
            response = oauth.post(request_token_url, params=params)
            
            if response.status_code != 200:
                logging.error(f"Failed to get request token: {response.text}")
                raise Exception(f"X API error: {response.status_code}")
                
            # Parse response
            response_params = dict(parse_qsl(response.text))
            oauth_token = response_params.get('oauth_token')
            oauth_token_secret = response_params.get('oauth_token_secret')
            
            return {
                'oauth_token': oauth_token,
                'oauth_token_secret': oauth_token_secret
            }
        except Exception as e:
            logging.error(f"Error getting X request token: {str(e)}")
            raise e
    
    def handle_callback(self, oauth_token, oauth_verifier, user_id):
        """
        Step 3: Convert the request token into a usable access token
        """
        try:
            # Create OAuth1 session
            oauth = OAuth1Session(
                client_key=os.environ.get('X_API_KEY'),
                client_secret=os.environ.get('X_KEY_SECRET'),
                resource_owner_key=oauth_token
            )
            
            # Get access token
            access_token_url = "https://api.x.com/oauth/access_token"
            params = {"oauth_verifier": oauth_verifier}
            response = oauth.post(access_token_url, params=params)
            
            if response.status_code != 200:
                logging.error(f"Failed to get access token: {response.text}")
                raise Exception(f"X API error: {response.status_code}")
                
            # Parse response
            response_params = dict(parse_qsl(response.text))
            access_token = response_params.get('oauth_token')
            access_token_secret = response_params.get('oauth_token_secret')
            
            # Store tokens in database
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                user.x_access_token = self.fernet.encrypt(access_token.encode()).decode()
                user.x_access_token_secret = self.fernet.encrypt(access_token_secret.encode()).decode()
                user.x_connected = True
                db.commit()
                
            return True
        except Exception as e:
            logging.error(f"Error handling X callback: {str(e)}")
            raise e

class X_Client_Handler:
    def __init__(self, user_id: int) -> None:
        try:
            self.user_id = user_id
            self.fernet = Fernet(os.environ.get('ENCRYPTION_KEY').encode())
            
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.x_connected or not user.x_access_token:
                    raise ValueError("User not connected to X or missing access token")
                
                self.access_token = self.fernet.decrypt(user.x_access_token.encode()).decode()
                self.access_token_secret = self.fernet.decrypt(user.x_access_token_secret.encode()).decode()
            
            # Create OAuth1 session for API requests
            self.oauth = OAuth1Session(
                client_key=os.environ.get('X_API_KEY'),
                client_secret=os.environ.get('X_KEY_SECRET'),
                resource_owner_key=self.access_token,
                resource_owner_secret=self.access_token_secret
            )
        except Exception as e:
            logging.error(f"Error initializing X client: {str(e)}")
            raise e
    
    def post_tweet_text(self, text: str, in_reply_to_tweet_id: str = None) -> str:
        """Post a tweet to X, if in_reply_to_tweet_id is provided, the tweet will be a reply to that tweet"""
        try:
            url = "https://api.x.com/2/tweets"
            payload = {"text": text}
            if in_reply_to_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": in_reply_to_tweet_id}
            response = self.oauth.post(url, json=payload)
            response_json = response.json()

            if "errors" in response_json:
                errors = response_json.get("errors",[])
                raise Exception(f"X API error: {response.status_code} - {errors}")
            if response.status_code not in [200, 201]:
                error_obj = response.text
                raise Exception(f"X API error: {response.status_code} - {error_obj}")
            
            # Extract tweet ID from the response
            tweet_id = response_json.get('data', {}).get('id')
            return tweet_id
        except Exception as e:
            logging.error(f"Error posting to X: {str(e)}")
            raise e
    

    def create_thread_text(self, tweets:list) -> None:
        try:
            previous_tweet_id = None
            for tweet in tweets:
                previous_tweet_id = self.post_tweet_text(tweet, previous_tweet_id)
        except Exception as e:
            logging.error(f"Error creating thread: {str(e)}")
            raise e
        
    def upload_media(self, media_path: str) -> str:
        try:
            url = "https://upload.twitter.com/1.1/media/upload.json"
            
            # Read the media file
            with open(media_path, 'rb') as media_file:
                files = {'media': media_file}
                response = self.oauth.post(url, files=files)
            
            if response.status_code != 200 and response.status_code != 201:
                logging.error(f"Failed to upload media: {response.status_code} {response.text}")
                raise Exception(f"X API error: {response.status_code}")
            
            # Get the media ID from the response
            media_id = response.json().get('media_id_string')
            return media_id
            
        except Exception as e:
            logging.error(f"Error uploading media: {str(e)}")
            raise e
    
    def post_tweet_media(self, text: str, media_id: str, in_reply_to_tweet_id: str = None) -> str:
        """Post a tweet with media attached to X, if in_reply_to_tweet_id is provided, the tweet will be a reply to that tweet"""
        try:
            url = "https://api.x.com/2/tweets"
            payload = {
                "text": text,
                "media": {
                    "media_ids": [media_id]
                }
            }
            if in_reply_to_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": in_reply_to_tweet_id}
                
            response = self.oauth.post(url, json=payload)
            
            if response.status_code not in [200, 201]:
                logging.error(f"Failed to post media tweet to X: {response.status_code} {response.text}")
                raise Exception(f"X API error: {response.status_code}")
            
            if response.status_code == 200:
                tweet_id = response.json().get('data', {}).get('id')
                return tweet_id
        except Exception as e:
            logging.error(f"Error posting media tweet to X: {str(e)}")
            raise e
    
    def create_thread_first_tweet_media(self, first_tweet_text: str, media_id: str, follow_up_tweets: list) -> None:
        """Create a thread where the first tweet has media and the rest are text-only"""
        try:
            # Post the first tweet with media
            first_tweet_id = self.post_tweet_media(first_tweet_text, media_id)
            if not first_tweet_id:
                raise Exception("Failed to post the first tweet with media")
            
            # Post the follow-up tweets as replies in the thread
            previous_tweet_id = first_tweet_id
            for tweet_text in follow_up_tweets:
                tweet_id = self.post_tweet_text(tweet_text, previous_tweet_id)
                if tweet_id:
                    previous_tweet_id = tweet_id
        except Exception as e:
            logging.error(f"Error creating mixed media thread: {str(e)}")
            raise e
        
    def check_endpoint_rate_limit(self, endpoint: str) -> dict:
        """
        Get the current rate limit status for a specific endpoint
        
        Args:
            endpoint: The endpoint to check, e.g., "tweets", "users", etc.
        
        Returns:
            A dictionary with limit, remaining, and reset time information
        """
        try:
            # Map of endpoints to sample API calls that will return rate limit info
            endpoint_urls = {
                "tweets": "https://api.x.com/2/tweets"
                # Add more endpoints as needed
            }
            
            if endpoint not in endpoint_urls:
                raise ValueError(f"Endpoint {endpoint} not supported for rate limit checking")
                
            url = endpoint_urls[endpoint]
            response = self.oauth.post(url)
            
            # Extract rate limit headers
            limit = response.headers.get('x-rate-limit-limit')
            remaining = response.headers.get('x-rate-limit-remaining')
            reset = response.headers.get('x-rate-limit-reset')
            
            # Format the reset time to make it more readable
            reset_time = datetime.fromtimestamp(int(reset)) if reset else None
            
            rate_limit_info = {
                "endpoint": endpoint,
                "limit": limit,
                "remaining": remaining,
                "reset_epoch": reset,
                "reset_time": reset_time,
                "status_code": response.status_code
            }
            
            return rate_limit_info
        except Exception as e:
            logging.error(f"Error checking rate limit for {endpoint}: {str(e)}")
            raise e

if __name__ == "__main__":
    try:
        x = X_Client_Handler(31)
        print(x.create_thread_text(["Test1", "Test2"]))
        #print(x.check_endpoint_rate_limit("tweets"))
    except Exception as e:
        print(f"Error testing X API: {str(e)}")
