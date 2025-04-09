from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
from app.airflow.dags.default_args import default_args
from app.database.database import SessionLocal
from app.database.models import Schedule
from app.core.helper_handlers import AirflowHandler
import logging

def check_and_trigger_schedules():
    """
    Checks active schedules and triggers the blog_analyse_task DAG 
    if the scheduled time has arrived. Updates the schedule's last_run_at time.
    """
    airflow_handler = AirflowHandler()
    now = datetime.now(timezone.utc)
    
    with SessionLocal() as db:
        active_schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        
        for schedule in active_schedules:
            if schedule.last_run_at is None or now >= (schedule.last_run_at + timedelta(minutes=schedule.minutes)):
                logging.info(f"Schedule {schedule.id} for user {schedule.user_id} is due. Triggering blog analysis for URL: {schedule.url}")
                try:
                    conf = {
                        "url": schedule.url,
                        "user_id": schedule.user_id,
                        "schedule_id": schedule.id
                    }
                    airflow_handler.trigger_dag('blog_analyse_task', conf=conf)
                    
                    # Update last_run_at immediately after triggering
                    schedule.last_run_at = now
                    db.commit()
                    logging.info(f"Successfully triggered blog_analyse_task for schedule {schedule.id} and updated last_run_at.")
                    
                except Exception as e:
                    db.rollback() # Rollback the last_run_at update if triggering fails
                    logging.error(f"Failed to trigger blog_analyse_task for schedule {schedule.id}: {str(e)}")
            else:
                logging.debug(f"Schedule {schedule.id} is not due yet. Last run: {schedule.last_run_at}, Interval: {schedule.minutes} mins.")


with DAG(
    'schedule_checker_dag',
    default_args=default_args,
    description='Checks active schedules and triggers blog analysis tasks periodically.',
    schedule_interval='*/1 * * * *',  # Run every minute
    start_date=datetime(2023, 1, 1),
    catchup=False,
    is_paused_upon_creation=False
) as dag:
    
    check_schedules_task = PythonOperator(
        task_id='check_and_trigger_schedules',
        python_callable=check_and_trigger_schedules,
    )