from flask import Flask, render_template, Blueprint, redirect, flash, url_for, request
from flask_login import login_required, current_user
import os
from ..forms import UrlSubmit, PromptForm, ProfileForm, ArticleCompareForm, BlogForm, SetupProfileForm,SettingsForm
from ..content_processor import ContentProcessor, ProfileComparer, BlogHandler
from ..database.database import SessionLocal
from ..database.models import Prompt, Profile, User
import asyncio
from ..api.article_operations import get_user_articles
import logging
from cryptography.fernet import Fernet
from ..api.prompt_operations import get_prompt


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

@bp.route('/home',methods=['GET','POST'])
@login_required
def base():
    form = UrlSubmit()
    result = None

    if form.validate_on_submit():
        try:
            processor = ContentProcessor(current_user)
            result = asyncio.run(processor.process_url(form.url.data))
        except Exception as e:
            result = {
                "status":"error",
                "message": f"An error occured: {str(e)}"
            }

    return render_template('index.html', form=form, result=result)

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
        return redirect(url_for('base.base'))

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
   
@bp.route('/profile', methods = ['GET','POST'])
@login_required
def profile():
    db = SessionLocal()
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    
    profile_form = ProfileForm(obj=profile) if profile else ProfileForm()
    article_comparison_form = ArticleCompareForm()
    comparison_result = None
    db.close()
    return render_template('profile.html', 
                        profile_form=profile_form, 
                        article_comparison_form=article_comparison_form,
                        comparison_result=comparison_result)

@bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    db = SessionLocal()
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    profile_form = ProfileForm(obj=profile)
    if profile_form.validate_on_submit():
        try:
            profile.full_name = profile_form.full_name.data
            profile.bio = profile_form.bio.data
            profile.interests_description = profile_form.interests_description.data
            profile.user_id = current_user.id
            db.commit()
            flash('Profile updated successfully','success')
            return redirect(url_for('base.profile'))
        except Exception as e:
            db.rollback()
            flash(f'Error updating profile {str(e)}') 
    db.close()
    return redirect(url_for('base.profile'))
    
@bp.route('/profile/compare',methods=['POST'])
@login_required
async def compare_article():
    logging.getLogger().setLevel(logging.ERROR)
    db = SessionLocal()
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    article_comparison_form = ArticleCompareForm()
    comparison_result = None
    if article_comparison_form.validate_on_submit():
        try:
            comparer = ProfileComparer(current_user)
            comparison_result = await comparer.compare_article_to_profile(
                article_url=article_comparison_form.article_url.data,
                user_id=current_user.id
            )
            flash('Article comparison completed', 'success')
        except Exception as e:
            flash(f'Error comparing the articles {str(e)}')
    db.close()
    return render_template('profile.html', 
                         profile_form=ProfileForm(obj=profile), 
                         article_comparison_form=article_comparison_form,
                         comparison_result=comparison_result)

@bp.route('/blogs' ,methods=['GET','POST'])
@login_required
async def blogs():
    form = BlogForm()
    result = None

    if form.validate_on_submit():
        try:
            print('Setting up blog handler')
            blog_handler = BlogHandler(current_user)
            print('Starting the processing and storing of articles')
            result = await blog_handler.process_and_store_articles(form.url.data,current_user.id)
            print('articles processed')
        except Exception as e:
                result = {
                "status": "error",
                "message": f"An error occurred: {str(e)}"
                }
    return render_template('blogs.html',form=form,result=result)

@bp.route('/processed-articles', methods=['GET'])
@login_required
def processed_articles():
    db = SessionLocal()
    try:
        articles = get_user_articles(db,current_user.id)
        return render_template('processed_articles.html', 
                             articles=articles)
    except Exception as e:
        flash(f'Error loading articles: {str(e)}', 'error')
        return redirect(url_for('base.base'))
    finally:
        db.close()

@bp.route('/onboarding',methods=['GET','POST'])
@login_required
def onboarding():
    if current_user.is_onboarded:
        return redirect(url_for('base.base'))
    
    db= SessionLocal()
    form = SetupProfileForm()

    if form.validate_on_submit():
        try:
            profile = Profile(
                user_id = current_user.id,
                username = current_user.email.split('@')[0],
                full_name = form.full_name.data,
                bio = form.bio.data,
                interests_description = form.interests_description.data
            )
            user = db.query(User).get(current_user.id)
            user.is_onboarded = True
            user.openai_api_key = fernet.encrypt(form.openai_api_key.data.encode())
            db.add(profile)
            db.commit()

            flash('Profile Created Successfully!','success')
            return redirect(url_for('base.base'))
        except Exception as e:
            db.rollback()
            flash('Error creating the profile','error')
            print(f'Error creating the profile {str(e)} ')
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
            user.openai_api_key = fernet.encrypt(form.openai_api_key.data.encode())
            db.commit()
            flash('Settings updated successfully', 'success')
            return redirect(url_for('base.settings'))
        except Exception as e:
            db.rollback()
            flash(f'Error updating settings: {str(e)}', 'error')
        finally:
            db.close()
    elif request.method == 'GET':
        form.openai_api_key.data = '********************************************************************'
    
    db.close()
    return render_template('settings.html', form=form)