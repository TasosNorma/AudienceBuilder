from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from app.airflow.tasks.draft_functions import draft_draft

default_args = {
    'owner': 'audiencebuilder',
    'depends_on_past': False, #It doesn't depend on any past dag to finish so that it can run
    'email_on_failure': False, #We don't want to send emails on failure
    'email_on_retry': False, #We don't want to send emails on retry
    'retries': 0 #We don't want to retry the task
}

# This DAG will be triggered manually by the API, not scheduled
with DAG(
    'draft_draft_task',
    default_args=default_args,
    description='Process a draft from a URL',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
        # Extract parameters from the DAG run configuration
        params = kwargs['dag_run'].conf
        url = params.get('url')
        prompt_id = params.get('prompt_id')
        user_id = params.get('user_id')
        
        if not all([url, prompt_id, user_id]):
            raise ValueError("Missing required parameters: url, prompt_id, or user_id")
        
        return draft_draft(url=url, prompt_id=int(prompt_id), user_id=int(user_id))
    
    draft_task = PythonOperator(
        task_id='draft_draft',
        python_callable=task_wrapper,
    )