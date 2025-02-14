from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from ..core.forms import LoginForm, RegistrationForm
from ..database.database import SessionLocal
from ..database.models import User
from ..api.onboarding_operations import create_new_user

auth_bp = Blueprint('auth',__name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('base.actions'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login',methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db = SessionLocal()
        user = db.query(User).filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('base.actions'))
        flash('Invalid email opr password')
        db.close()
    return render_template('login.html',form=form)

@auth_bp.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('actions.base'))
    form = RegistrationForm()
    if form.validate_on_submit():
        db = SessionLocal()
        try:
            if db.query(User).filter_by(email=form.email.data).first():
                flash('Email already registered')
                return render_template('auth/register.html', form=form)
            
            create_new_user(email=form.email.data, password=form.password.data)
            flash('Registration successful! Please login.')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.rollback()
            flash(f'Registration failed: {str(e)}')
        finally:
            db.close()
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))