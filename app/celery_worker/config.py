import os
from celery import Celery
from kombu import Queue, Exchange
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'db+' + os.getenv('DATABASE_URL')
beat_dburi = os.getenv('DATABASE_URL')

celery_app = Celery(
    'content_processor',     # Name of application
    broker=CELERY_BROKER_URL,     # URL for the message broker (Redis)
    backend=CELERY_RESULT_BACKEND,  # Where to store task results (Supabase)
    include=['app.celery_worker.tasks']  # Python modules to import when workers start
)
# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Queue settings
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('content_processing', Exchange('content_processing'), routing_key='content_processing'),
    ),
    
    # Route tasks to specific queues
    task_routes={
        'app.celery_worker.tasks.generate_post': {'queue': 'content_processing'},
        'app.celery_worker.tasks.compare_profile_task':{'queue':'content_processing'},
        'app.celery_worker.tasks.blog_analyse': {'queue': 'content_processing'},
        'app.celery_worker.tasks.generate_linkedin_informative_post_from_comparison': {'queue': 'content_processing'},
        'app.celery_worker.tasks.redraft_linkedin_post_from_comparison': {'queue': 'content_processing'}
    },
    
    # Task execution settings
    task_time_limit=1800,  # 30 minutes max runtime
    task_soft_time_limit=1500,  # Soft limit 25 minutes
    
    # Result settings
    result_expires=86400,  # Results expire in 24 hours

    # Beat Schedule_Handler settings
    beat_dburi= beat_dburi,  
    beat_scheduler='sqlalchemy_celery_beat.schedulers:DatabaseScheduler',
)