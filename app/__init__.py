from flask import Flask
from flask_login import LoginManager
import os
import logging
import warnings
from urllib3.exceptions import NotOpenSSLWarning
from flask_wtf.csrf import CSRFProtect
warnings.filterwarnings('ignore', category=NotOpenSSLWarning)

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)

    from app.routes.base_routes import bp as base_bp
    from app.routes.auth_routes import auth_bp as auth_bp
    # Create the manager
    login_manager = LoginManager()
    # Connect it to our Flask app
    login_manager.init_app(app)
    # Tell it which page to show when someone needs to log in
    login_manager.login_view = 'auth.login'
    # This function tells Flask-Login how to find a specific user
    @login_manager.user_loader
    def load_user(user_id):
        from app.database.models import User
        from app.database.database import SessionLocal
        db = SessionLocal()
        user = db.query(User).get(int(user_id))
        db.close()
        return user

    app.debug = True
    logging.basicConfig(level=logging.DEBUG)
    app.register_blueprint(base_bp)
    app.register_blueprint(auth_bp)
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
    csrf.init_app(app)

    # Disable Flask development server logging
    app.logger.disabled = True
    logging.getLogger('werkzeug').disabled = True
    
    return app