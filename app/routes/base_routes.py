from flask import Flask, render_template, Blueprint, redirect, flash, url_for, request, jsonify, json
from flask_login import login_required, current_user
import os
from ..core.forms import UrlSubmit, PromptForm, SetupProfileForm,SettingsForm, ScheduleForm,ProfileForm, ArticleCompareForm
from ..database.database import SessionLocal
from ..database.models import Prompt, Profile, User, ProcessingResult,Schedule, Blog, BlogProfileComparison
import logging
from cryptography.fernet import Fernet
from celery_worker.tasks import process_url_task
from datetime import datetime,timezone
from celery_worker.config import beat_dburi
from ..api.general import Scheduler, Profile_Handler, Blog_Analysis_Handler, Blog_Profile_Comparison_Handler,Processing_Result_Handler
from flask_wtf.csrf import generate_csrf
from json import JSONDecodeError 



bp = Blueprint('base', __name__)
fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())

@bp.before_request
def check_onboarding():
    # We open a new database connection to give the flask-login the info about the profile of the user that are needed for the profile section of the sidebar
    if current_user.is_authenticated:
        db = SessionLocal()        
        try:
            db.add(current_user)  
            if not current_user.is_onboarded and request.endpoint != 'base.onboarding':
                return redirect(url_for('base.onboarding'))
        finally:
            db.close()

@bp.route('/')
def index():
    try:
        return redirect(url_for('base.actions'))
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}", exc_info=True)
        return f"An error occurred: {str(e)}", 500

@bp.route('/process_url',methods=['GET','POST'])
@login_required
def process_url():
    form = UrlSubmit()
    result = None
    db = SessionLocal()

    try:
        processing_history = db.query(ProcessingResult)\
            .filter(ProcessingResult.user_id == current_user.id)\
            .order_by(ProcessingResult.created_at_utc.desc())\
            .limit(10)\
            .all()
    except Exception as e:
        logging.error(f"Error fetching processing history: {str(e)}")
        processing_history = []
    finally:
        db.close()

    db = SessionLocal()
    if form.validate_on_submit():
        try:
            # Create pending record immediately
            processing_result = ProcessingResult(
                user_id=current_user.id,
                url=form.url.data,
                status="pending",
                created_at_utc=datetime.now(timezone.utc)
            )
            db.add(processing_result)
            db.commit()
            # Start the task and add the ID to the database
            task = process_url_task.delay(form.url.data, current_user.id, processing_result.id)
            processing_result.task_id = task.id
            db.commit()
            result = {
                "status": "processing",
                "message": "Your request is being processed.",
                "task_id": task.id,
                "result_id": processing_result.id
            }
            
        except Exception as e:
            result = {
                "status": "error",
                "message": f"An error occurred: {str(e)}"
            }
        finally:
            db.close()
    return render_template('index.html', form=form, result=result, processing_history=processing_history)

@bp.route('/prompts', methods =['GET','POST'])
@login_required
def prompts():
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(Prompt.user_id == current_user.id, Prompt.type == 1).first()
        # Create a prompt object that will be placed inside the form for a placeholder in order to showcase only the relevant parts of the prompt
        modified_prompt = prompt
        parts = modified_prompt.template.split("### Suffix_")
        editable_template = parts[0] if len(parts) >1 else ''
        modified_prompt.template = editable_template
    except Exception as e:
        logging.error(f"Error in prompts route: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('base.actions'))

    if modified_prompt:
        form = PromptForm(obj=modified_prompt)
    else:
        form = PromptForm()

    # Change the name and the template of the prompt
    if form.validate_on_submit():
        try:
            prompt.name = form.name.data
            prompt.template = f"{form.template.data.strip()} \n ### Suffix_ {parts[1]}"
            db.commit()
            print(f"Prompt template : {prompt.template}")
            flash('Prompt updated successfully', 'success')
            return redirect(url_for('base.prompts'))
        except Exception as e:
            db.rollback()
            flash(f'Error updating prompt {str(e)}','error')
    
    db.close()
    return render_template('prompts.html', form=form)
   
@bp.route('/onboarding',methods=['GET','POST'])
@login_required
def onboarding():
    if current_user.is_onboarded:
        return redirect(url_for('base.actions'))
    
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
            user.phone_number = form.phone_number.data
            encrypted_api_key = fernet.encrypt(form.openai_api_key.data.encode())
            user.openai_api_key = encrypted_api_key.decode()
            db.add(profile)
            db.commit()

            flash('Profile Created Successfully!','success')
            return redirect(url_for('base.actions'))
        except Exception as e:
            db.rollback()
            flash(f'Error creating the profile{str(e)}','error')
        finally:
            db.close()
    
    return render_template('onboarding.html',form=form)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = SessionLocal()
    form = SettingsForm()
    
    if form.validate_on_submit():
        try:
            user = db.query(User).get(current_user.id)
            user.openai_api_key = fernet.encrypt(form.openai_api_key.data.encode()).decode()

            phone = form.phone_number.data.strip()
            user.phone_number = phone
            db.commit()
            flash('Settings updated successfully', 'success')
            return redirect(url_for('base.settings'))
        except Exception as e:
            db.rollback()
            logging.error(f'Error updating settings: {str(e)}')
            flash(f'Error updating settings: {str(e)}', 'error')
        finally:
            db.close()
    elif request.method == 'GET':
        form.openai_api_key.data = '********************************************************************'
        form.phone_number.data = current_user.phone_number
    
    db.close()
    return render_template('settings.html', form=form)

@bp.route('/schedule', methods=['GET','POST'])
@login_required
def schedule():
    form = ScheduleForm()
    result = None
    db = SessionLocal()
    schedule_handler = Scheduler(current_user.id)
    
    try:
        # Add logging to track execution
        logging.info("Fetching schedules for user_id: %s", current_user.id)
        
        # Get user's schedules
        schedules = db.query(Schedule)\
            .filter(Schedule.user_id == current_user.id)\
            .order_by(Schedule.created_at.desc())\
            .all()
        
        csrf_token = generate_csrf()
        
        logging.info("Found %d schedules and generated csrf", len(schedules))
            
        if form.validate_on_submit():
            result = schedule_handler.create_blog_schedule(
                url=form.url.data,
                minutes=form.minutes.data
            )
            if result["status"] == "success":
                return redirect(url_for('base.schedule'))
                
        return render_template('schedule.html', 
                             form=form, 
                             result=result, 
                             schedules=schedules,
                             csrf_token=csrf_token)
    except Exception as e:
        # Add detailed error logging
        logging.error("Error in schedule route: %s", str(e), exc_info=True)
        # Return a user-friendly error page instead of 500
        flash('An error occurred while loading schedules', 'error')
        return render_template('schedule.html', 
                             form=form, 
                             result={"status": "error", "message": "Failed to load schedules"}, 
                             schedules=[])
    finally:
        db.close()

@bp.route('/schedule/<int:schedule_id>')
@login_required
def schedule_profile(schedule_id):
    try:
        schedule_handler = Scheduler(current_user.id)
        result = schedule_handler.get_schedule_profile(schedule_id)
        
        if result["status"] == "error":
            flash(result["message"], 'error')
            return redirect(url_for('base.schedule'))
            
        return render_template('schedule_profile.html', schedule=result["schedule"])
    except Exception as e:
        logging.error(f"Error in schedule detail route: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('base.schedule'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = SessionLocal()
    form = ProfileForm()
    try:
        profile = db.query(Profile).filter_by(user_id=current_user.id).first()

        if form.validate_on_submit():
            try:
                result = Profile_Handler.change_interests_description(
                    user_id=current_user.id,
                    new_description=form.interests_description.data
                )
                logging.info(f"Successfully updated profile interests for user {current_user.id}")
            except Exception as e:
                logging.error(f"Failed to update profile interests: {str(e)}")
                result = {"status": "error", "message": "Failed to update profile"}
        elif request.method == 'GET':
            form.interests_description.data = profile.interests_description

        return render_template('profile.html', form=form, profile=profile)
    except Exception as e:
        logging.error(f"Error in profile route: {str(e)}", exc_info=True)
        return redirect(url_for('base.actions'))
    finally:
        db.close()

@bp.route('/profile_compare', methods=['GET', 'POST'])
@login_required
def profile_compare():
    form = ArticleCompareForm()
    result = None

    if form.validate_on_submit():
        result = Profile_Handler.create_profile_comparison(
            user_id=current_user.id,
            url=form.article_url.data
        )
        if result["status"] == "success":
            flash('Profile comparison initiated successfully', 'success')
            return redirect(url_for('base.profile_compare'))
        else:
            flash(result["message"], 'error')
    
    # Get existing comparisons
    comparisons_result = Profile_Handler.get_user_comparisons(current_user.id)
    comparisons = comparisons_result.get("comparisons", [])

    return render_template(
        'profile_comparisons.html',
        form=form,
        result=result,
        comparisons=comparisons
    )

@bp.route('/profile_comparison/<int:comparison_id>')
@login_required
def profile_comparison_detail(comparison_id):
    result = Profile_Handler.get_comparison_details(comparison_id, current_user.id)
    comparison = result["comparison"]
    return render_template(
        'profile_comparison_detail.html',
        comparison = comparison
    )

@bp.route('/processing_result/<int:result_id>', methods=['GET'])
@login_required
def processing_result(result_id):
    logging.info(f"Accessing processing_result for ID: {result_id}")
    db = SessionLocal()
    try:
        logging.info(f"Querying database for result_id: {result_id} and user_id: {current_user.id}")
        result = db.query(ProcessingResult)\
            .filter(ProcessingResult.id == result_id, ProcessingResult.user_id == current_user.id)\
            .first()
        
        if not result:
            logging.warning(f"No result found for ID: {result_id}")
            flash('Processing result not found', 'error')
            return redirect(url_for('base.actions'))
            
        tweets = []
        if result.tweets:
            try:
                # First attempt: direct JSON parsing
                tweets = json.loads(result.tweets)
                logging.info("Successfully parsed tweets using direct JSON loading")
            except json.JSONDecodeError:
                # Second attempt: clean the string and try again
                logging.info("Direct JSON parsing failed, attempting string cleanup")
                tweets_str = result.tweets.replace('\\"', '"').strip('"')
                tweets = json.loads(tweets_str)
                logging.info("Successfully parsed tweets after string cleanup")
        logging.info(f"Processed {len(tweets)} tweets") 
        return render_template('processing_result.html', result=result, tweets=tweets)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing tweets JSON: {str(e)}")
        flash('Error parsing tweets data', 'error')
        return redirect(url_for('base.actions'))
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('base.actions'))
    finally:
        db.close()

@bp.route('/blog/<int:blog_id>')
@login_required
def blog_detail(blog_id):
    db = SessionLocal()
    try:
        # Get blog and its comparisons
        blog = db.query(Blog)\
            .filter_by(id=blog_id, user_id=current_user.id)\
            .first()
        
        if not blog:
            flash('Blog not found or access denied', 'error')
            return redirect(url_for('base.blog_analysis'))
        
        comparisons = db.query(BlogProfileComparison)\
            .filter_by(blog_id=blog_id)\
            .order_by(BlogProfileComparison.created_at.desc())\
            .all()
        
        return render_template('blog_details.html', blog=blog, comparisons=comparisons)
    except Exception as e:
        logging.error(f"Error in blog detail route: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('base.blog_analysis'))
    finally:
        db.close()

@bp.route('/blog_comparison/<int:comparison_id>',methods=['GET', 'POST'])
@login_required
def blog_comparison_detail(comparison_id):
    try:
        comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
        processing_handler = Processing_Result_Handler(current_user.id)
        comparison = comparison_handler.get_comparison_by_id(comparison_id=comparison_id)["comparison"]
        if comparison.processing_result_id:
            processing_result = comparison_handler.get_processing_result_of_comparison(comparison_id=comparison_id)["processing_result"]
            parts= processing_handler.get_tweet_in_parts(processing_result.id)["parts"]
        else:
            processing_result = None
            parts = None
        return render_template('blog_comparison_detail.html', comparison=comparison, processing_result=processing_result,parts=parts)
    except Exception as e:
        logging.error(f"Couldn't get comparison with id {comparison_id} error: {e}")
        return redirect(url_for('base.actions'))

@bp.route('/blog_analysis', methods=['GET', 'POST'])
@login_required
def blog_analysis():
    form = UrlSubmit() 
    db = SessionLocal()
    
    try:
        # Get user's blogs
        blogs = db.query(Blog)\
            .filter(Blog.user_id == current_user.id)\
            .order_by(Blog.created_at.desc())\
            .all()
        
        if form.validate_on_submit():
            result = Blog_Analysis_Handler.create_blog_analyse_session(
                user_id=current_user.id,
                url=form.url.data
            )
        return render_template('blog_analysis.html', form=form, blogs=blogs)
    except Exception as e:
        logging.error(f"Error in blog analysis route: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('base.blog_analysis'))
    finally:
        db.close()

@bp.route('/relevant_blog_comparison_list')
@login_required
def blog_comparison_list(): 
    # All possible statuses for the filter form
    all_statuses = ["Ignored Article", "Drafted Post", "Posted", "Ignored Draft", "Notified User", "Failed"]
    # Get selected statuses from query parameters, default to all relevant statuses if none selected
    selected_statuses = request.args.getlist('statuses') or all_statuses
    
    blog_profile_handler = Blog_Profile_Comparison_Handler(current_user.id)
    result = blog_profile_handler.get_user_comparisons_by_whatsapp_status(
        whatsapp_statuses=selected_statuses
    )
    
    comparisons = result.get("comparisons", [])
    
    return render_template(
        'relevant_blog_comparison_list.html', 
        comparisons=comparisons,
        all_statuses=all_statuses,
        selected_statuses=selected_statuses
    )

@bp.route('/actions')
@login_required
def actions():
    # All possible statuses for the filter form
    all_statuses = ["Notified User", "Drafted Post", "Posted", "Ignored Article", "Ignored Draft", "Failed","Drafting Post"]
    selected_statuses = request.args.getlist('statuses') or ["Notified User", "Drafted Post"]
    comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
    result = comparison_handler.get_user_comparisons_by_whatsapp_status(
        whatsapp_statuses=selected_statuses
    )
    
    comparisons = result.get("comparisons", [])
    
    return render_template(
        'actions.html', 
        comparisons=comparisons,
        all_statuses=all_statuses,
        selected_statuses=selected_statuses
    )
