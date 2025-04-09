from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from app.airflow.tasks.draft_functions import draft_draft, draft_action, draft_group
from app.airflow.dags.default_args import default_args

# This DAG will be triggered manually by the API, not scheduled
with DAG(
    'draft_draft_task',
    default_args=default_args,
    description='Draft from a URL',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
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

with DAG(
    'draft_action_task',
    default_args=default_args,
    description='Draft from an action',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
        params = kwargs['dag_run'].conf
        user_id = params.get('user_id')
        action_id = params.get('action_id')
        prompt_id = params.get('prompt_id')
        
        if not all([user_id, action_id, prompt_id]):
            raise ValueError("Missing required parameters: user_id, action_id, or prompt_id")
        
        return draft_action(user_id=int(user_id), action_id=int(action_id), prompt_id=int(prompt_id))   
    
    draft_action_task = PythonOperator(
        task_id='draft_action',
        python_callable=task_wrapper,
    )
    


with DAG(
    'draft_group_task',
    default_args=default_args,
    description='Draft from a group',
    schedule_interval=None,  # Manual triggers only
    start_date=datetime(2023, 1, 1),
    catchup=False, # It catches up to everything that it has missed since the start date, useful if we ever try to turn this into a scheduled dag. 
    is_paused_upon_creation=False
) as dag:
    
    def task_wrapper(**kwargs):
        """Wrapper function to handle parameters from Airflow"""
        params = kwargs['dag_run'].conf
        group_id = params.get('group_id')
        prompt_id = params.get('prompt_id')
        user_id = params.get('user_id')
        
        if not all([group_id, prompt_id, user_id]):
            raise ValueError("Missing required parameters: group_id, prompt_id, or user_id")
        
        return draft_group(group_id=int(group_id), prompt_id=int(prompt_id), user_id=int(user_id))
    
    draft_group_task = PythonOperator(
        task_id='draft_group',
        python_callable=task_wrapper,
    )

