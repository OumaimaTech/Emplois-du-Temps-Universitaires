from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from config import config
from models import db, User, Admin, Teacher, Student
from routes import create_blueprints
import os

def create_app(config_name='development'):
    """Configure et initialise l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    create_blueprints(app)
    
    with app.app_context():
        db.create_all()
    
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if isinstance(current_user, Admin):
                return redirect(url_for('admin.dashboard'))
            elif isinstance(current_user, Teacher):
                return redirect(url_for('teacher.dashboard'))
            elif isinstance(current_user, Student):
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))
    return app

if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    app.run(debug=True, host='0.0.0.0', port=5000)
