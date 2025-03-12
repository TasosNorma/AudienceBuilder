import os
from celery import Celery
from kombu import Queue, Exchange
from dotenv import load_dotenv
import logging
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
        'app.celery_worker.tasks.generate_linkedin_informative_post_from_url': {'queue': 'content_processing'},
        'app.celery_worker.tasks.compare_profile_task':{'queue':'content_processing'},
        'app.celery_worker.tasks.blog_analyse': {'queue': 'content_processing'},
        'app.celery_worker.tasks.generate_linkedin_informative_post_from_comparison': {'queue': 'content_processing'},
        'app.celery_worker.tasks.redraft_linkedin_post_from_comparison': {'queue': 'content_processing'},
        'app.celery_worker.tasks.redraft_post_task': {'queue': 'content_processing'},
        'app.celery_worker.tasks.comparison_draft': {'queue': 'content_processing'}
    },
    
    # Task execution settings
    task_time_limit=2600,  # 43 minutes max runtime
    task_soft_time_limit=2400,  # Soft limit 40 minutes
    
    # Result settings
    result_expires=86400,  # Results expire in 24 hours

    # Beat Schedule_Handler settings
    beat_dburi= beat_dburi,  
    beat_scheduler='sqlalchemy_celery_beat.schedulers:DatabaseScheduler',
        beat_engine_options={
        # Only include connect_args which are compatible with NullPool
        'connect_args': {
            'connect_timeout': 10,      # Maximum time to wait for database connection in seconds
            'keepalives': 1,            # Enable TCP keepalive packets
            'keepalives_idle': 30,      # Seconds of idle time before sending keepalive
            'keepalives_interval': 10,  # Seconds between keepalive probes
            'keepalives_count': 5,      # Number of failed probes before connection is dropped
            'sslmode': 'require',       # Enforce SSL connection
            'application_name': 'celery-beat',  # Identify application in database logs
        },
    },
    
    # Beat scheduler retry settings
    beat_max_loop_interval=60,          # Maximum interval between beat loop iterations (seconds)
    beat_sync_every=10, 

    # Flower settings
    flower_inspect_timeout=5000,
    flower_persistent=True,
    flower_db='flower.db',
)