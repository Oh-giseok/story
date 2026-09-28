import os
from datetime import datetime
from flask import Flask, redirect, render_template, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # 업로드 폴더 설정
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'reels_uploads')

    upload_folder = os.path.join(app.root_path, 'static', 'photo')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['POST_UPLOAD_FOLDER'] = upload_folder

    # 설정 로드
    app.config.from_object('config')

    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-secret-key'

    # ORM 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # 1. 모델을 가장 먼저 로드 (Flask-SocketIO나 Blueprint보다 먼저 메타데이터 등록)
    from . import models

    # 2. SocketIO 초기화 및 로드
    from story.events import socketio
    socketio.init_app(app, cors_allowed_origins="*")

    with app.app_context():
        db.create_all()

    # 3. 블루프린트 임포트 및 등록 (중복 제거)
    from story.views import auth_views, dmviews, main_views, post_views, story_views
    from .views.Reels_views import reels_bp

    app.register_blueprint(reels_bp)
    app.register_blueprint(main_views.bp)
    app.register_blueprint(dmviews.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(post_views.bp)
    app.register_blueprint(story_views.bp)

    # 라우트 설정
    @app.route('/')
    def index():
        return redirect(url_for('post._list'))

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

    # 템플릿 필터
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