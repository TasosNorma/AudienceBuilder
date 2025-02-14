from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from .database import Base
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.orm import relationship 

class Prompt(Base):
    __tablename__ = 'prompts'

    id = Column(Integer, primary_key=True)
    type = Column(Integer,nullable=False)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer,ForeignKey('users.id'), nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)
    input_variables = Column(Text, nullable=True)  # Stored as JSON string
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc))
    user = relationship('User',back_populates='prompts')
    
class Profile(Base):
    __tablename__ = 'profiles'

    # Primary Data
    id = Column(Integer,primary_key=True)
    user_id = Column(Integer,ForeignKey('users.id'),nullable=False)
    username = Column(String(50), unique=True, nullable=True)
    full_name = Column(String(50),nullable=True)
    bio = Column(Text, nullable=True) # General description of the user
    interests_description = Column(Text,nullable=False) # Detailed description of the user
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    user = relationship('User',back_populates='profile')
    
class User(Base,UserMixin):
    __tablename__ = 'users'

    id = Column(Integer,primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(1024), nullable=False)
    is_active = Column(Boolean, default=True)
    phone_number = Column(String(20), nullable=True)
    openai_api_key = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    profile = relationship('Profile',back_populates='user', uselist=False)
    prompts = relationship('Prompt',back_populates='user')
    is_onboarded = Column(Boolean,default=False,nullable=True)
        
    def set_password(self, password, method='pbkdf2:sha256'):
        self.password_hash = generate_password_hash(password, method=method)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ProcessingResult(Base):
    __tablename__ = 'processing_results'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    url = Column(String(2048), nullable=False)
    status = Column(String(50), nullable=False)
    tweets = Column(Text, nullable=True)  # JSON string of tweets
    tweet_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    task_id = Column(String(50), nullable=True)
    created_at_utc = Column(DateTime, default=datetime.now(timezone.utc))
    whatsapp_triggered = Column(Boolean, default=False)
    message_sid = Column(String(50),nullable=True)
    posted = Column(Boolean, default=False)
    blog_comparison_id = Column(Integer, ForeignKey('blog_profile_comparisons.id'),nullable=True)

class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)
    minutes = Column(Integer, nullable=False)
    interval_schedule_id = Column(Integer, nullable=False)
    periodic_task_id = Column(Integer, nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

class ProfileComparison(Base):
    __tablename__ = 'profile_comparisons'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    profile_interests = Column(Text, nullable=False)  
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    url = Column(String(2048), nullable=False)
    short_summary = Column(Text, nullable=True)
    comparison_result = Column(Text, nullable=True)  
    status = Column(String(50), default='pending', nullable=False)  # pending, completed, failed

class Blog(Base):
    __tablename__ = 'blogs'

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default='pending', nullable=False)
    number_of_articles = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    number_of_fitting_articles = Column(Integer, default=0)
    schedule_id = Column(Integer, ForeignKey('schedules.id'),nullable=True)

class BlogProfileComparison(Base):
    __tablename__ = 'blog_profile_comparisons'

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    blog_id = Column(Integer, ForeignKey('blogs.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    short_summary = Column(Text, nullable=True)
    profile_interests = Column(Text, nullable=True)
    comparison_result = Column(Text, nullable=True)  # Will store the detailed comparison results
    status = Column(String(50), default='pending', nullable=False)  # pending, completed, failed
    whatsapp_status = Column(String(50), nullable=True,default='not_processed') # not_processed,ignored, processing, posted
    message_sid = Column(String(50),nullable=True)
    processing_result_id = Column(Integer, ForeignKey('processing_results.id'),nullable=True)
    error_message = Column(Text, nullable=True)
    schedule_id = Column(Integer, ForeignKey('schedules.id'),nullable=True)