from ..database.database import SessionLocal
from ..database.models import Schedule,User,BlogProfileComparison,Post,Prompt
from ..celery_worker.config import beat_dburi
from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, Period
from sqlalchemy_celery_beat.session import SessionManager
import logging
from datetime import datetime
import json

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
                task='celery_worker.tasks.blog_analyse',
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

            logging.info(f"Successfully created scheduled task '{interval_task.name}' with interval {interval_schedule.every} {interval_schedule.period}")
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
                    logging.info(f"Updated comparison {comparison_id} status to {new_status}")
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
                    name = Prompt.NAME_NORMALPOSTGENERATIONPROMPT,
                    type=Prompt.TYPE_POSTGENERATING,
                    description = 'Generates viral post from article content',
                    user_id = user_id,
                    template = """
            You are a professional Twitter writer who focuses on business, data analytics, AI, and related news. Your goal is to craft engaging Twitter threads that attract and inform your audience, ultimately building a following for future entrepreneurial ventures.

            **Thread Structure & Guidelines:**

            1. **Hook (First Tweet):**
                - **Purpose:** Grab attention and entice readers. Make them understand it's about news and not personal opinions.
                - **Content:** Start with a bold statement or a compelling question related to the main topic. Be objective and highlight the key value proposition or benefit.
                - **Length:** Keep under 280 characters.
                - **Style:** Use concise and impactful language.
            2. **Body (Middle parts):**
                - **Purpose:** Deliver key information and insights.
                - **Content:** Break down the main points from the articles into digestible pieces. Incorporate relevant data, quotes, or statistics to add value.
                - **Flow:** Ensure a natural progression between parts for readability.
                - **Length:** Each tweet should be under 280 characters.
                - **Style:** Maintain clear and readable sentences.
            3. **Call-to-Action (Final Tweet):**
                - **Purpose:** Drive engagement.
                - **Content:** Include a clear directive that encourages interaction, such as asking for thoughts or suggesting to follow for more insights.
                - **Alignment:** Make sure it aligns with the thread's content.
                - **Length:** Under 280 characters.

            **Additional Guidelines:**

            - **Tone:** Maintain a professional and informative voice while staying approachable. Focus on factual news reporting rather than sensationalism, particularly in the opening tweet.
            - **Audience Focus:** Tailor content to professionals interested in business, data analytics, and AI.
            - **Language:** Avoid jargon; keep it accessible to a broad audience.
            - **Originality:** While summarizing the articles, ensure the content is original and offers a unique perspective. 
            - **Facts-Based:** Don't comment with opinions, focus mainly on the facts that you can find in the articles. 
            ### Suffix_     

            You will be provided with one main article and additional secondary articles. The secondary articles are links referenced in the primary article.
            Your task is to write a compelling Twitter thread about the main article, enriching it with insights and context from the secondary articles. The thread should be informative, engaging, and encourage audience interaction.

            ** Primary Article **
            This is the primary article:
            {primary}


            ** Secondary Articles **
            These are the secondary articles.
            {secondary}

            """,
                input_variables='["primary", "secondary"]',
                is_active=True
                )
                db.add(default_prompt_2)
                db.add(default_prompt_1)
                db.commit()
                logging.info("Successfully added the default prompts for user %s", user_id)
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
    def get_prompt_template(cls,prompt_type: int, user_id: int):
        with SessionLocal() as db:
            try:
                prompt = db.query(Prompt).filter(
                    Prompt.type == prompt_type, 
                    Prompt.user_id == user_id
                ).first()
                if prompt:
                    return prompt.template
                else:
                    raise ValueError(f"No prompt found for type {prompt_type} and user {user_id}")
            except Exception as e:
                raise e