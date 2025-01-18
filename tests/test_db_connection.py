from app.database.database import init_db, SessionLocal
from app.database.models import User
from celery_sqlalchemy_scheduler.models import (
    ModelBase,
    IntervalSchedule,
    CrontabSchedule,
    PeriodicTask,
)
from app.database.database import engine

def test_connection():
    try:
        # Try to create all tables
        init_db()
        
        # Test connection by creating a session
        db = SessionLocal()
        
        # Try a simple query
        users = db.query(User).all()
        print("✅ Database connection successful!")
        print(f"Found {len(users)} users in database")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

def init_scheduler_tables():
    # Create all scheduler-related tables
    ModelBase.metadata.create_all(engine)
    print("Successfully created celery scheduler tables")

if __name__ == "__main__":
    test_connection()
    init_scheduler_tables()