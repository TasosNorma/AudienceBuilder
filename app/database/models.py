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

    user = relationship('User', backref='processing_results')


class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)
    minutes = Column(Integer, nullable=False)
    interval_schedule_id = Column(Integer, nullable=False)
    periodic_task_id = Column(Integer, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship('User', backref='schedules')