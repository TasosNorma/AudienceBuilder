from ..database.database import SessionLocal
from ..database.models import Schedule
from celery_worker.config import beat_dburi
from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, Period
from sqlalchemy_celery_beat.session import SessionManager
import logging
from datetime import datetime
import json

class Scheduler:
    @classmethod
    def create_schedule(cls, url: str, user_id: int,minutes: int) -> dict:
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

            task_name = f'process_url_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            
            interval_task = PeriodicTask(
                schedule_model=interval_schedule,
                name=task_name,
                task='celery_worker.tasks.process_url_task_no_processing_id',
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
    
