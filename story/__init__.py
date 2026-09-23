from flask import Flask
from story.models import db

def create_app():
    app=Flask(__name__)
    app.config.from_object('config')
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///story.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
    db.init_app(app)
    from story.events import socketio
    socketio.init_app(app,cors_allowed_origins="*")
    from story.views import mainviews,dmviews
    app.register_blueprint(mainviews.bp)
    app.register_blueprint(dmviews.bp)
    return app