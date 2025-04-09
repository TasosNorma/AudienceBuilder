from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from app.airflow.tasks.blog_functions import blog_analyse
from app.airflow.dags.default_args import default_args

with DAG(
    'blog_analyse_task',
    default_args=default_args,
    description='Analyse a blog',
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
        schedule_id = params.get('schedule_id', None)

        if not all([url, user_id]):
            raise ValueError("Missing required parameters: url and user_id")
        
        return blog_analyse(url=url, user_id=user_id, schedule_id=schedule_id)
    
    blog_analyse_task = PythonOperator(
        task_id='blog_analyse',
        python_callable=task_wrapper,
    )