from flask import Flask
import os

from flask import Flask, render_template
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# db 객체를 __init__.py에서 생성하여 순환 참조 방지
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'reels_uploads')

    # 기본 설정
    app.config.from_object('config')

    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-secret-key'

    # 확장 플러그인 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # SocketIO 설정
    from story.events import socketio
    socketio.init_app(app, cors_allowed_origins="*")

    # DB 테이블 자동 생성
    with app.app_context():
        db.create_all()

    # 블루프린트 등록
    from story.views import main_views, dmviews, auth_views

    from . import models

    from  .views.Reels_views import reels_bp
    app.register_blueprint(reels_bp)

    #블루프린트

    app.register_blueprint(main_views.bp)
    app.register_blueprint(dmviews.bp)
    app.register_blueprint(auth_views.bp)

    @app.route('/')
    def index():
        return "flask team project"

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

