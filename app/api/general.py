from ..database.database import SessionLocal
from ..database.models import Schedule, Profile,ProfileComparison,User,Blog,BlogProfileComparison
from celery_worker.config import beat_dburi
from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, Period
from sqlalchemy_celery_beat.session import SessionManager
import logging
from datetime import datetime
import json
from celery_worker.tasks import compare_profile_task,blog_analyse

class Scheduler:
        
    @classmethod
    def create_blog_schedule(cls, url: str, user_id: int,minutes: int) -> dict:
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

            task_name = f'Blog_Analysis{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            
            interval_task = PeriodicTask(
                schedule_model=interval_schedule,
                name=task_name,
                task='celery_worker.tasks.blog_analyse',
                args=json.dumps([url, user_id]),
                kwargs=json.dumps({}),
                description='Scheduled URL processing task'
            )
            beat_session.add(interval_task)
            beat_session.flush()  # Flush to get the ID

            # Create user schedule record
            schedule = Schedule(
                user_id=user_id,
                name=task_name,
                url=url,
                minutes=minutes,
                interval_schedule_id=interval_schedule.id,
                periodic_task_id=interval_task.id
            )
            app_db.add(schedule)
            
            # Commit both sessions
            beat_session.commit()
            app_db.commit()

            logging.info(f"Successfully created scheduled task '{interval_task.name}' with interval {interval_schedule.every} {interval_schedule.period}")
            
            return {
                "status": "success",
                "message": f"Successfully scheduled task to process URL every {interval_schedule.every} {interval_schedule.period}"
            }
            
        except Exception as e:
            beat_session.rollback()
            app_db.rollback()
            logging.error(f"Error creating scheduled task: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to schedule task: {str(e)}"
            }
        finally:
            beat_session.close()
            app_db.close()

    @classmethod
    def disable_schedule(cls,schedule_id:int) -> dict:
        app_db = SessionLocal()
        session_manager = SessionManager()
        beat_session = session_manager.session_factory(beat_dburi)

        try:
            # Get the schedule from our application database
            schedule = app_db.query(Schedule).filter_by(id=schedule_id).first()
            if not schedule:
                return {
                    "status": "error",
                    "message": f"Schedule with id {schedule_id} not found"
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
            
            return {
                "status": "success",
                "message": f"Successfully disabled the schedule with id {schedule_id}"
            }
        except Exception as e:
            beat_session.rollback()
            app_db.rollback()
            logging.error(f"Error disabling schedule: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to disable schedule: {str(e)}"
            }
        finally:
            beat_session.close()
            app_db.close()
    
class Profile_Handler:
    @classmethod
    def change_interests_description(cls,user_id:int,new_description: str) -> dict:
        db = SessionLocal()
        try:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            if not profile:
                return {
                    "status": "error",
                    "message": "Profile not found"
                }
            
            profile.interests_description = new_description
            db.commit()
            logging.info(f"Successfully updated interests description for user {user_id}")
            return {
                "status": "success",
                "message": "Interests description updated successfully"
            }
        except Exception as e:
            db.rollback()
            logging.error(f"Error updating interests description: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to update interests description: {str(e)}"
            }
        finally:
            db.close()

    @classmethod
    def create_profile_comparison(cls, user_id: int, url: str) -> dict:
        db = SessionLocal()
        try:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            if not profile:
                return {
                "status": "error",
                "message": "User profile not found"
                }
            # Create profile comparison record
            profile_comparison = ProfileComparison(
                user_id=user_id,
                url=url,
                status="pending",
                created_at=datetime.utcnow(),
                profile_interests=profile.interests_description 
            )
            db.add(profile_comparison)
            db.commit()
            db.refresh(profile_comparison)

            # Invoke celery task
            compare_profile_task.delay(profile_comparison.id, user_id)
            logging.info(f"Successfully created profile comparison with ID {profile_comparison.id} for user {user_id}")

            return {
                "status": "success",
                "message": "Profile comparison initiated",
                "comparison_id": profile_comparison.id
            }
        except Exception as e:
            db.rollback()
            logging.error(f"Error creating profile comparison: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to create profile comparison: {str(e)}"
            }
        finally:
            db.close()
    
    @classmethod
    def get_user_comparisons(cls, user_id: int) -> dict:
        db = SessionLocal()
        try:
            comparisons = db.query(ProfileComparison).filter_by(user_id=user_id).order_by(ProfileComparison.created_at.desc()).all()
            return {
                "status": "success",
                "comparisons": comparisons
            }
        except Exception as e:
            logging.error(f"Error fetching user comparisons: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to fetch comparisons: {str(e)}"
            }
        finally:
            db.close()

    @classmethod
    def get_comparison_details(cls, comparison_id: int, user_id: int) -> dict:
        db = SessionLocal()
        try:
            comparison = (
                db.query(ProfileComparison)
                .filter_by(id=comparison_id, user_id=user_id)
                .first()
            )
            
            if not comparison:
                return {
                    "status": "error",
                    "message": "Comparison not found or access denied"
                }
                
            return {
                "status": "success",
                "comparison": {
                    "id": comparison.id,
                    "url": comparison.url,
                    "status": comparison.status,
                    "created_at": comparison.created_at,
                    "comparison_result": comparison.comparison_result,
                    "short_summary": comparison.short_summary,
                    "profile_interests": comparison.profile_interests
                }
            }
        except Exception as e:
            logging.error(f"Error fetching comparison details: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to fetch comparison details: {str(e)}"
            }
        finally:
            db.close()
    
class Blog_Analysis_Handler:
    @classmethod
    def create_blog_analyse_session(cls,user_id:int, url:str) -> dict:
        try:
            blog_analyse.delay(user_id = user_id , url = url)
            logging.info(f"Blog Analysis was initiated")
            return {
                    "status": "success",
                    "message": "Blog analysis inititated",
                }
        except Exception as e:
            logging.error(f"Error creating blog analysis: {str(e)}")
            with SessionLocal() as db:
                blog = Blog(
                    user_id=user_id,
                    url=url,
                    status="failed",
                    error_message=str(e)
                )
                db.add(blog)
                db.commit()
            return {
                "status": "error", 
                "message": f"Failed to create blog analysis: {str(e)}"
            }
    
class Blog_Profile_Comparison_Handler:
    # Takes a list of whatsap_statuses and return comparisons order by created_at
    @classmethod
    def get_user_comparisons_by_whatsapp_status(cls, user_id: int, whatsapp_statuses: list[str]) -> dict:
        db = SessionLocal()
        try:
            comparisons = (
                db.query(BlogProfileComparison)
                .filter(
                    BlogProfileComparison.user_id == user_id,
                    BlogProfileComparison.whatsapp_status.in_(whatsapp_statuses)
                )
                .order_by(BlogProfileComparison.created_at.desc())
                .all()
            )
            return {
                "status": "success",
                "comparisons": comparisons
            }
        except Exception as e:
            logging.error(f"Error fetching user comparisons by WhatsApp status: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to fetch comparisons: {str(e)}"
            }
        finally:
            db.close()