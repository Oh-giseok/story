from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# db 객체를 __init__.py에서 생성하여 순환 참조 방지
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

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

    # [수정] DB 테이블 자동 생성 (기존 run.py의 db.create_all() 통합)
    with app.app_context():
        db.create_all()

    # 블루프린트 등록
    from story.views import mainviews, dmviews
    app.register_blueprint(mainviews.bp)
    app.register_blueprint(dmviews.bp)

    @app.route('/')
    def index():
        return "flask team project"

    return app

if __name__ == '__main__':
    from story.events import socketio
    app = create_app()
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)