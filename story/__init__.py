import os

from flask import Flask, render_template
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'dev-secret-key'
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'reels_uploads')

    migrate = Migrate()



    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    migrate.init_app(app, db)

    from . import models

    from  .views.Reels_views import reels_bp
    app.register_blueprint(reels_bp)


    @app.route('/')
    def index():
        return "flaks team project"

    return app
