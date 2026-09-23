import os
from flask import Flask, redirect, render_template, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'reels_uploads')

    # 게시물 이미지 업로드 폴더
    upload_folder = os.path.join(app.root_path, 'static', 'photo')
    os.makedirs(upload_folder, exist_ok=True)

    app.config['POST_UPLOAD_FOLDER'] = upload_folder

    app.config.from_object('config')

    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-secret-key'

    db.init_app(app)
    migrate.init_app(app, db)

    from story.events import socketio
    socketio.init_app(app, cors_allowed_origins="*")

    with app.app_context():
        db.create_all()

    from story.views import main_views, dmviews, auth_views, post_views, story_views

    from . import models

    from .views.Reels_views import reels_bp

    app.register_blueprint(reels_bp)
    app.register_blueprint(main_views.bp)
    app.register_blueprint(dmviews.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(post_views.bp)
    app.register_blueprint(story_views.bp)

    @app.route('/')
    def index():
        return redirect(url_for('post._list'))

    # 스토리 목록 페이지 추가
    @app.route('/story')
    def story_list():
        now = datetime.now()

        story_list = models.Story.query.filter(
            models.Story.expires_at > now
        ).order_by(
            models.Story.create_date.desc()
        ).all()

        return render_template(
            'story/story_list.html',
            story_list=story_list
        )

    # 스토리 작성 시간을 인스타그램 스타일로 표시
    @app.template_filter('time_ago')
    def time_ago_filter(value):
        if not value:
            return ""

        diff = datetime.now() - value

        seconds = diff.total_seconds()
        minutes = int(seconds // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)

        if minutes < 1:
            return "방금 전"
        elif minutes < 60:
            return f"{minutes}분 전"
        elif hours < 24:
            return f"{hours}시간"
        else:
            return f"{days}일 전"

    return app


if __name__ == '__main__':
    from story.events import socketio

    app = create_app()
    socketio.run(
        app,
        host='127.0.0.1',
        port=5000,
        debug=True
    )
