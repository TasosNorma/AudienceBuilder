from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from app.airflow.tasks.profile_functions import compare_profile, ignore_and_learn
from app.airflow.dags.default_args import default_args

with DAG(
    'profile_compare_task',
    default_args=default_args,
    description='Compare a profile to a url',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
        params = kwargs['dag_run'].conf
        url = params.get('url')
        user_id = params.get('user_id')
        
        if not all([url, user_id]):
            raise ValueError("Missing required parameters: url, or user_id")
        
        return compare_profile(url=url, user_id=int(user_id))
    
    profile_compare_task = PythonOperator(
        task_id='compare_profile',
        python_callable=task_wrapper,
    )

with DAG(
    'ignore_and_learn_task',
    default_args=default_args,
    description='Ignore and learn a profile',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
        params = kwargs['dag_run'].conf
        user_id = params.get('user_id')
        comparison_id = params.get('comparison_id')
        
        if not all([user_id, comparison_id]):
            raise ValueError("Missing required parameters: user_id, or comparison_id")
        
        return ignore_and_learn(user_id=user_id, comparison_id=comparison_id)
    
    ignore_and_learn_task = PythonOperator(
        task_id='ignore_and_learn',
        python_callable=task_wrapper,
    )
