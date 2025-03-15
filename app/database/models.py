from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from .database import Base
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Prompt(Base):
    __tablename__ = 'prompts'

    #Allowed Types
    TYPE_ARTICLE = 1
    TYPE_ARTICLE_DEEP_RESEARCH = 2


    id = Column(Integer, primary_key=True)
    type = Column(Integer,nullable=False)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer,ForeignKey('users.id'), nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)
    input_variables = Column(Text, nullable=True)  # Stored as JSON string
    deep_research_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc))
    
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
    
class User(Base,UserMixin):
    __tablename__ = 'users'

    id = Column(Integer,primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(1024), nullable=False)
    is_active = Column(Boolean, default=True)
    phone_number = Column(String(20), nullable=True)
    openai_api_key = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_onboarded = Column(Boolean,default=False,nullable=True)
    # LinkedIn Authentication Fields
    linkedin_access_token = Column(String(1024), nullable=True)
    linkedin_access_token_expires_in = Column(Integer, nullable=True)
    linkedin_refresh_token = Column(String(1024), nullable=True)
    linkedin_refresh_token_expires_in = Column(Integer, nullable=True)
    linkedin_scope = Column(String(255), nullable=True)
    linkedin_connected = Column(Boolean, default=False)
        
    def set_password(self, password, method='pbkdf2:sha256'):
        self.password_hash = generate_password_hash(password, method=method)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(Base):
    __tablename__ = 'posts'

    # Allowed Statuses
    FAILED = 'Failed'
    GENERATED = 'Generated'
    POSTED_LINKEDIN = 'Posted LinkedIn'
    PROCESSING = 'Processing'
    REDRAFTING = 'Redrafting'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    url = Column(String(2048), nullable=False)
    status = Column(String(50), nullable=False)
    parts = Column(Text, nullable=True)  
    part_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at_utc = Column(DateTime, default=datetime.now(timezone.utc))
    blog_comparison_id = Column(Integer, ForeignKey('blog_profile_comparisons.id'),nullable=True)
    markdown_text = Column(Text, nullable=True)  
    plain_text = Column(Text, nullable=True) 

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

    # Allowed Statuses
    FAILED = 'Failed'
    PROCESSING = 'Processing'
    COMPLETED = 'Completed'


    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    profile_interests = Column(Text, nullable=False)  
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    url = Column(String(2048), nullable=False)
    short_summary = Column(Text, nullable=True)
    comparison_result = Column(Boolean, nullable=True)  
    error_message = Column(Text, nullable=True)
    status = Column(String(50), default=PROCESSING, nullable=False)  # processing, completed, failed

class Blog(Base):
    __tablename__ = 'blogs'

    # Allowed Statuses
    FAILED = 'Failed'
    PROCESSING = 'Processing'
    COMPLETED = 'Completed'

    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default=PROCESSING, nullable=False)
    number_of_articles = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    number_of_fitting_articles = Column(Integer, default=0)
    schedule_id = Column(Integer, ForeignKey('schedules.id'),nullable=True)

class BlogProfileComparison(Base):
    __tablename__ = 'blog_profile_comparisons'

    # Allowed Statuses
    STATUS_FAILED_ON_COMPARISON = 'Failed on Comparison' # Failed while performing the comparison 
    STATUS_COMPARING = 'Comparing' # Comparison in Progress
    STATUS_PROCESSED_IN_PAST_BLOG = 'Processed in Past Blog' # URl was processed in previous blog
    STATUS_DEEMED_NOT_RELEVANT = 'Deemed Not Relevant' # URL was deemed not relevant to profile
    STATUS_ACTION_PENDING_TO_DRAFT = 'Action Pending to Draft' # Finished comparison and pending first action, to draft or ignore
    STATUS_DRAFTING = 'Drafting' # Currently Drafting
    STATUS_REDRAFTING = 'Redrafting' # Currently Drafting
    STATUS_INGNORED_COMPARISON = 'Ignored Comparison' # Chose to ingore comparison and not draft
    STATUS_ACTION_PENDING_TO_POST = 'Action Pending to Post' # Drafting was completed and pending another action, to post or ignore
    STATUS_INGORED_DRAFT = 'Ingored Draft' # Ingored the Draft
    STATUS_POSTED_LINKEDIN = 'Posted LinkedIn' # Posted
    STATUS_FAILED_ON_DRAFT = 'Failed on Draft' # Failed while generating draft
    STATUS_FAILED = 'Failed' #This is on random failures not attributed to important tasks


    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(2048), nullable=True)
    blog_id = Column(Integer, ForeignKey('blogs.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    short_summary = Column(Text, nullable=True)
    profile_interests = Column(Text, nullable=True)
    comparison_result = Column(Boolean, nullable=True)  # Will store whether the article matches the profile
    status = Column(String(50), default='pending', nullable=False)  # pending, completed, failed
    post_id = Column(Integer, ForeignKey('posts.id'),nullable=True)
    error_message = Column(Text, nullable=True)
    schedule_id = Column(Integer, ForeignKey('schedules.id'),nullable=True)
    past_blog_id = Column(Integer, ForeignKey('blogs.id'),nullable=True)