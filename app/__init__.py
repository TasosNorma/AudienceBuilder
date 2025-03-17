from flask import Flask
from flask_login import LoginManager
import os
import logging
import warnings
from urllib3.exceptions import NotOpenSSLWarning
from flask_wtf.csrf import CSRFProtect
warnings.filterwarnings('ignore', category=NotOpenSSLWarning)

def create_app():
    app = Flask(__name__)

    from app.routes.template_routes import tmpl 
    from app.routes.api_routes import api 
    # Create the manager
    login_manager = LoginManager()
    # Connect it to our Flask app
    login_manager.init_app(app)
    # Tell it which page to show when someone needs to log in
    login_manager.login_view = 'tmpl.login'
    # This function tells Flask-Login how to find a specific user
    @login_manager.user_loader
    def load_user(user_id):
        from app.database.models import User
        from app.database.database import SessionLocal
        db = SessionLocal()
        user = db.query(User).get(int(user_id))
        db.close()
        return user

    app.debug = False
    logging.basicConfig(level=logging.WARNING)
    app.register_blueprint(api)
    app.register_blueprint(tmpl)
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Disable Flask development server logging
    app.logger.disabled = True
    logging.getLogger('werkzeug').disabled = True
    
    return app