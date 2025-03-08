from flask import render_template, Blueprint, redirect, flash, url_for, request, session
from flask_login import login_required, current_user, login_user, logout_user
import os
from ..core.forms import UrlSubmit, PromptForm, SetupProfileForm,SettingsForm, ScheduleForm,ProfileForm, ArticleCompareForm, LoginForm, RegistrationForm
from ..database.database import SessionLocal
from ..database.models import Prompt, Profile, User, Post,Schedule, Blog, BlogProfileComparison,ProfileComparison
import logging
from cryptography.fernet import Fernet
from ..core.helper_handlers import Schedule_Handler, User_Handler, LinkedIn_Auth_Handler
from flask_wtf.csrf import generate_csrf
from time import sleep
from urllib.parse import urlencode
from app.celery_worker.tasks import compare_profile_task, blog_analyse,generate_linkedin_informative_post_from_url
import secrets
import markdown
import re
from sqlalchemy import case

tmpl = Blueprint('tmpl', __name__)
fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())


@tmpl.before_request
def check_onboarding():
    # We open a new database connection to give the flask-login the info about the profile of the user that are needed for the profile section of the sidebar
    if current_user.is_authenticated:
        with SessionLocal() as db:
            db.add(current_user)  
            if not current_user.is_onboarded and request.endpoint != 'tmpl.onboarding':
                return redirect(url_for('tmpl.onboarding'))

@tmpl.route('/login',methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        with SessionLocal() as db:
            user = db.query(User).filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for('tmpl.actions'))
            flash('Invalid email opr password')
    return render_template('login.html',form=form)

@tmpl.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('tmpl.actions'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        with SessionLocal() as db:
            try:
                if db.query(User).filter_by(email=form.email.data).first():
                    flash('Email already registered')
                    return redirect(url_for('tmpl.register'))
                user_handler = User_Handler()
                user_handler.create_new_user(email=form.email.data, password=form.password.data)
                flash('Registration successful! Please login.')
                return redirect(url_for('tmpl.login'))
            except Exception as e:
                flash(f'Registration failed: {str(e)}')
                return redirect(url_for('tmpl.login'))
    return render_template('register.html', form=form)

@tmpl.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('tmpl.actions'))
    return redirect(url_for('tmpl.login'))

@tmpl.route('/onboarding',methods=['GET','POST'])
@login_required
def onboarding():
    if current_user.is_onboarded:
        return redirect(url_for('tmpl.actions'))
    
    db= SessionLocal()
    form = SetupProfileForm()

    if form.validate_on_submit():
        try:
            profile = Profile(
                user_id = current_user.id,
                username = current_user.email.split('@')[0],
                full_name = form.full_name.data,
                interests_description = form.interests_description.data
            )
            user = db.query(User).get(current_user.id)
            user.is_onboarded = True
            encrypted_api_key = fernet.encrypt(form.openai_api_key.data.encode())
            user.openai_api_key = encrypted_api_key.decode()
            db.add(profile)
            db.commit()

            flash('Profile Created Successfully!','success')
            return redirect(url_for('tmpl.actions'))
        except Exception as e:
            db.rollback()
            flash(f'Error creating the profile{str(e)}','error')
        finally:
            db.close()
    
    return render_template('onboarding.html',form=form)

@tmpl.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('tmpl.login'))

@tmpl.route('/actions', methods=['GET'])
@login_required
def actions():
    # All possible statuses for the filter form
    all_statuses = [
        BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST,
        BlogProfileComparison.STATUS_ACTION_PENDING_TO_DRAFT,
        BlogProfileComparison.STATUS_DRAFTING,
        BlogProfileComparison.STATUS_INGNORED_COMPARISON,
        BlogProfileComparison.STATUS_INGORED_DRAFT,
        BlogProfileComparison.STATUS_POSTED_LINKEDIN,
        BlogProfileComparison.STATUS_FAILED,
        BlogProfileComparison.STATUS_FAILED_ON_COMPARISON,
        BlogProfileComparison.STATUS_FAILED_ON_DRAFT,
        BlogProfileComparison.STATUS_COMPARING,
        BlogProfileComparison.STATUS_PROCESSED_IN_PAST_BLOG,
        BlogProfileComparison.STATUS_DEEMED_NOT_RELEVANT
    ]
    selected_statuses = request.args.getlist('statuses') or [
        BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST, BlogProfileComparison.STATUS_ACTION_PENDING_TO_DRAFT,
        BlogProfileComparison.STATUS_DRAFTING, BlogProfileComparison.STATUS_REDRAFTING
    ]
    with SessionLocal() as db:
        comparisons = (
            db.query(BlogProfileComparison)
            .filter(
                BlogProfileComparison.user_id == current_user.id,
                BlogProfileComparison.status.in_(selected_statuses)
            )
            .order_by(
                case(
                    (BlogProfileComparison.status == BlogProfileComparison.STATUS_ACTION_PENDING_TO_POST, 0),
                    else_=1
                ),
                BlogProfileComparison.created_at.desc()
            )
            .all()
        )
    return render_template('actions.html', comparisons=comparisons,all_statuses=all_statuses,selected_statuses=selected_statuses)

@tmpl.route('/action/<int:comparison_id>',methods=['GET', 'POST'])
@login_required
def action_profile(comparison_id):
    with SessionLocal() as db:
        try:
            parts = None
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            post = db.query(Post).filter(Post.blog_comparison_id==comparison_id, Post.user_id==current_user.id).first()
            return render_template('action_profile.html', comparison=comparison, post=post, Post = Post)
        except Exception as e:
            logging.error(f"Couldn't get comparison with id {comparison_id} error: {e}")
            flash(f"Unexpected error: {str(e)}", 'error')
            return redirect(url_for('tmpl.actions'))

@tmpl.route('/drafts',methods=['GET','POST'])
@login_required
def drafts():
    form = UrlSubmit()
    processing_history = []
    with SessionLocal() as db:
        processing_history = db.query(Post)\
            .filter(Post.user_id == current_user.id)\
            .order_by(Post.created_at_utc.desc())\
            .limit(10)\
            .all()

    if form.validate_on_submit():
        generate_linkedin_informative_post_from_url.delay(form.url.data,current_user.id)
        flash('Post Generation started. Please wait while we process your request.', 'info')
        sleep(1) # We do this to make sure that the the record will be created and will be in processing state.
        return(redirect(url_for('tmpl.drafts')))
    return render_template('drafts.html', form=form, processing_history=processing_history)

@tmpl.route('/draft/<int:post_id>', methods=['GET'])
@login_required
def draft_profile(post_id):
    with SessionLocal() as db:
        try:
            post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
            return render_template('draft_profile.html', post=post)
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            flash(f"Unexpected error: {str(e)}", 'error')
            return redirect(url_for('tmpl.drafts'))

@tmpl.route('/prompts', methods =['GET','POST'])
@login_required
def prompts():
    try:
        with SessionLocal() as db:
            prompt = db.query(Prompt).filter(Prompt.user_id == current_user.id, Prompt.type == 1).first()
            # Remove the ### Suffix_ of the prompt. These are the {Primary} and {Secondary} Articles.
            modified_prompt = prompt
            parts = modified_prompt.template.split("### Suffix_")
            editable_template = parts[0] if len(parts) >1 else ''
            modified_prompt.template = editable_template
            form = PromptForm(obj=modified_prompt)
            # Change the name and the template of the prompt
            if form.validate_on_submit():
                prompt.name = form.name.data
                prompt.template = f"{form.template.data.strip()} \n ### Suffix_ {parts[1]}"
                db.commit()
                flash('Prompt updated successfully', 'success')
                return redirect(url_for('tmpl.prompts'))
    except Exception as e:
        flash(f'Error updating prompt: {str(e)}', 'error')
        return redirect(url_for('tmpl.prompts'))
    return render_template('prompts.html', form=form)
   
@tmpl.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    with SessionLocal() as db:
        try:
            profile = db.query(Profile).filter_by(user_id=current_user.id).first()
            form = ProfileForm(obj=profile)
            if form.validate_on_submit():
                profile.interests_description = form.interests_description.data
                db.commit()
                flash("Profile updated successfully", "success")
                return redirect(url_for('tmpl.profile'))
            return render_template('profile.html', form=form, profile=profile)
        except Exception as e:
            logging.error(f"Error in profile route: {str(e)}")
            flash(f'Error updating profile: {str(e)}', 'error')
            return redirect(url_for('tmpl.profile'))

@tmpl.route('/profile_compare', methods=['GET', 'POST'])
@login_required
def profile_compare():
    form = ArticleCompareForm()
    result = None
    with SessionLocal() as db:
        try:
            if form.validate_on_submit():
                compare_profile_task.delay(user_id=current_user.id,url=form.article_url.data)
                sleep(1)
                flash('Comparison started. Please wait while we process your request.', 'info')
                return redirect(url_for('tmpl.profile_compare'))
                
            # Get existing comparisons
            comparisons = db.query(ProfileComparison).filter_by(user_id=current_user.id).order_by(ProfileComparison.created_at.desc()).all()

            return render_template(
                'profile_comparisons.html',
                form=form,
                result=result,
                comparisons=comparisons
            )
        except Exception as e:
            logging.error(f"Error in profile_compare route: {str(e)}")
            flash(f'Error in profile_compare route: {str(e)}', 'error')
            return redirect(url_for('tmpl.profile_compare'))

@tmpl.route('/profile_comparison/<int:comparison_id>', methods=['GET'])
@login_required
def profile_comparison_profile(comparison_id):
    with SessionLocal() as db:
        comparison = db.query(ProfileComparison).filter_by(id=comparison_id, user_id=current_user.id).first()
        return render_template(
            'profile_comparison_profile.html',
            comparison = comparison
        )

@tmpl.route('/schedule', methods=['GET','POST'])
@login_required
def schedule():
    form = ScheduleForm()
    db = SessionLocal()
    schedule_handler = Schedule_Handler(current_user.id)
    
    try:
        schedules = db.query(Schedule).filter(Schedule.user_id == current_user.id).order_by(Schedule.created_at.desc()).all()
        csrf_token = generate_csrf()
            
        if form.validate_on_submit():
            schedule_handler.create_blog_schedule(
                url=form.url.data,
                minutes=form.minutes.data
            )
            sleep(0.5)
            flash('Schedule Added Successfully.', 'info')
            return redirect(url_for('tmpl.schedule'))
                
        return render_template('schedule.html', 
                             form=form,  
                             schedules=schedules,
                             csrf_token=csrf_token)
    except Exception as e:
        logging.error("Error in schedule route: %s", str(e), exc_info=True)
        flash(f"Error : {str(e)}", 'error')
        return render_template('schedule.html', 
                             form=form, 
                             result=str(e), 
                             schedules=schedules)
    finally:
        db.close()

@tmpl.route('/schedule/<int:schedule_id>', methods=['GET'])
@login_required
def schedule_profile(schedule_id):
    with SessionLocal() as db:
        try:
            schedule_obj = db.query(Schedule).filter_by(
                id=schedule_id, 
                user_id=current_user.id
            ).first()
            if not schedule_obj:
                flash("Schedule not found or access denied", "error")
                return redirect(url_for('tmpl.schedule'))        
            associated_blogs = db.query(Blog).filter_by(schedule_id=schedule_id).order_by(Blog.created_at.desc()).all()
            schedule = {
                "id": schedule_obj.id,
                "name": schedule_obj.name,
                "url": schedule_obj.url,
                "minutes": schedule_obj.minutes,
                "created_at": schedule_obj.created_at,
                "is_active": schedule_obj.is_active,
                "last_run_at": schedule_obj.last_run_at,
                "blogs": [
                    {
                        "id": blog.id,
                        "url": blog.url,
                        "status": blog.status,
                        "created_at": blog.created_at,
                        "number_of_articles": blog.number_of_articles,
                        "number_of_fitting_articles": blog.number_of_fitting_articles,
                        "error_message": blog.error_message
                    }
                    for blog in associated_blogs
                ]
            }
            return render_template('schedule_profile.html', schedule=schedule)
        
        except Exception as e:
            logging.error(f"Error in schedule detail route: {str(e)}")
            flash(f'An error occurred while processing your request: {str(e)}', 'error')
            return redirect(url_for('tmpl.schedule'))

@tmpl.route('/blogs', methods=['GET', 'POST'])
@login_required
def blogs():
    form = UrlSubmit() 
    db = SessionLocal()
    
    try:
        # Get user's blogs
        blogs = db.query(Blog)\
            .filter(Blog.user_id == current_user.id)\
            .order_by(Blog.created_at.desc())\
            .all()
        
        if form.validate_on_submit():
            blog_analyse.delay(user_id = current_user.id , url = form.url.data)
            flash('Blog Analysis started. Please wait while we process your request.', 'info')
            sleep(1)
            return(redirect(url_for('tmpl.blogs')))
        return render_template('blogs.html', form=form, blogs=blogs)
    except Exception as e:
        logging.error(f"Error in blog analysis route: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('tmpl.blogs'))
    finally:
        db.close()

@tmpl.route('/blog/<int:blog_id>', methods=['GET'])
@login_required
def blog_profile(blog_id):
    db = SessionLocal()
    try:
        # Get blog and its comparisons
        blog = db.query(Blog)\
            .filter_by(id=blog_id, user_id=current_user.id)\
            .first()
        
        if not blog:
            flash('Blog not found or access denied', 'error')
            return redirect(url_for('tmpl.blogs'))
        
        comparisons = db.query(BlogProfileComparison)\
            .filter_by(blog_id=blog_id)\
            .order_by(BlogProfileComparison.comparison_result.desc().nullslast(),  # True values first, then False, then nulls
                     BlogProfileComparison.created_at.desc())\
            .all()
        
        return render_template('blog_profile.html', blog=blog, comparisons=comparisons, BlogProfileComparison = BlogProfileComparison)
    except Exception as e:
        logging.error(f"Error in blog detail route: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('tmpl.blogs'))
    finally:
        db.close()

@tmpl.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = SessionLocal()
    form = SettingsForm()
    
    if form.validate_on_submit():
        try:
            user = db.query(User).get(current_user.id)
            user.openai_api_key = fernet.encrypt(form.openai_api_key.data.encode()).decode()
            db.commit()
            flash('Settings updated successfully', 'success')
            return redirect(url_for('tmpl.settings'))
        except Exception as e:
            db.rollback()
            logging.error(f'Error updating settings: {str(e)}')
            flash(f'Error updating settings: {str(e)}', 'error')
        finally:
            db.close()
    elif request.method == 'GET':
        form.openai_api_key.data = '********************************************************************'
    
    db.close()
    return render_template('settings.html', form=form)

@tmpl.route('/linkedin/auth',methods=['GET'])
@login_required
def linkedin_auth():
    try:
        state = secrets.token_hex(16)
        # Store the state in the session
        session['linkedin_state'] = state
        params = {
            'response_type': 'code',
            'client_id': os.environ['LINKEDIN_CLIENT_ID'],
            'redirect_uri': os.environ['LINKEDIN_CALLBACK_URL'],
            'state': state,
            'scope': 'profile openid w_member_social'
        }
        
        authorization_url = f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
        return redirect(authorization_url)
    except Exception as e:
        logging.error(f"Error during LinkedIn auth: {str(e)}")
        flash(f"LinkedIn authentication failed: {str(e)}", "error")
        return redirect(url_for('tmpl.settings'))
    
@tmpl.route('/linkedin/callback',methods=['GET'])
@login_required
def linkedin_callback():
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        
        # Verify the state to prevent CSRF attacks
        if state != session.get('linkedin_state'):
            flash('LinkedIn authentication failed: Invalid state parameter', 'danger')
            return redirect(url_for('tmpl.settings'))
        
        # Clear the state from the session
        session.pop('linkedin_state', None)

        # If the user denied access or there was an error
        if 'error' in request.args:
            error_description = request.args.get('error_description', 'Unknown error')
            flash(f'LinkedIn authentication failed: {error_description}', 'danger')
            return redirect(url_for('tmpl.settings'))
        
        # Handle the callback
        linkedin_auth = LinkedIn_Auth_Handler()
        linkedin_auth.handle_callback(code, current_user.id)
        return redirect(url_for('tmpl.settings'))
    except Exception as e:
        logging.error(f"Error during LinkedIn callback: {str(e)}")
        flash(f"LinkedIn authentication failed: {str(e)}", "error")
        return redirect(url_for('tmpl.settings'))
    
@tmpl.route('/linkedin/disconnect')
@login_required
def linkedin_disconnect():
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == current_user.id).first()
            
            user.linkedin_access_token = None
            user.linkedin_access_token_expires_in = None
            user.linkedin_refresh_token = None
            user.linkedin_refresh_token_expires_in = None
            user.linkedin_scope = None
            user.linkedin_connected = False

            db.commit()
            flash('LinkedIn account disconnected successfully', 'success')
        
        return redirect(url_for('tmpl.settings'))
    except Exception as e:
        logging.error(f"Error disconnecting LinkedIn account: {str(e)}")
        flash(f"Failed to disconnect LinkedIn account: {str(e)}", "error")
        return redirect(url_for('tmpl.settings'))
    

@tmpl.app_template_filter('markdown')
def markdown_filter(text):
    if text:
        # Here we take out the hashtags and we replace them with a span with class hashtag, otherwise they appear as H1 in UI
        hashtag_pattern = r'#(\w+)'
        html = markdown.markdown(text)
        html = re.sub(hashtag_pattern, r'<span class="hashtag">#\1</span>', html)
        return html
    return ''

@tmpl.app_template_filter('nl2br')
def nl2br_filter(text):
    if not text:
        return ""
    return text.replace('\n', '<br>')