import os
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, url_for, g, session
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from story.time_utils import as_utc, utc_now_naive, kst_now_naive, format_kst

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)

    # 업로드 폴더 설정
    app.config['UPLOAD_FOLDER'] = os.path.join(
        app.root_path, 'static', 'reels_uploads'
    )

    upload_folder = os.path.join(app.root_path, 'static', 'photo')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['POST_UPLOAD_FOLDER'] = upload_folder

    # 프로필 이미지는 정적 파일로 제공한다.
    profile_upload_folder = os.path.join(app.root_path, 'static', 'profile')
    os.makedirs(profile_upload_folder, exist_ok=True)
    app.config['PROFILE_UPLOAD_FOLDER'] = profile_upload_folder

    # 설정 로드
    app.config.from_object('config')

    # Render 같은 호스팅 환경의 값으로 개발 기본 설정을 덮어쓴다.
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', app.config.get('SECRET_KEY', 'dev-secret-key')
    )

    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite:'):
        engine_options = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {})
        connect_args = dict(engine_options.get('connect_args') or {})
        connect_args.setdefault('timeout', 30)
        engine_options['connect_args'] = connect_args
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-secret-key'

    # ORM 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_message = '로그인이 필요합니다.'
    login_message_category = 'info'

    @app.template_filter('profile_img')
    def profile_img_filter(img_url):
        if not img_url:
            return url_for('static', filename='photo/default_profile.png')
        if img_url.startswith('http://') or img_url.startswith('https://') or img_url.startswith('/'):
            return img_url
        if img_url.startswith('profile/') or img_url.startswith('photo/'):
            return url_for('static', filename=img_url)
        return url_for('static', filename='profile/' + img_url)

    @app.context_processor
    def inject_global_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return {'global_csrf_token': generate_csrf}

    # 모델 로드
    from . import models

    # Flask-Login 사용자 불러오기
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # SocketIO 초기화 및 로드
    from story.events import socketio
    socketio.init_app(app, cors_allowed_origins="*")

    with app.app_context():
        db.create_all()
        # create_all does not add columns to an existing database.
        from sqlalchemy import inspect, text
        user_columns = {column['name'] for column in inspect(db.engine).get_columns('user')}
        schema_changed = False
        if 'status' not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"))
            schema_changed = True
        if 'last_activity_at' not in user_columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN last_activity_at DATETIME'))
            schema_changed = True
        if 'deletion_requested_at' not in user_columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN deletion_requested_at DATETIME'))
            schema_changed = True
            if 'deleted_date' in user_columns:
                db.session.execute(text(
                    'UPDATE user SET deletion_requested_at = deleted_date '
                    'WHERE deleted_date IS NOT NULL'
                ))
        table_names = set(inspect(db.engine).get_table_names())
        if 'notification_new' in table_names:
            # Recover an interrupted prior run: keep the original table when it exists;
            # if it was already dropped, promote the copied table back to its name.
            with db.engine.begin() as connection:
                if 'notification' in table_names:
                    connection.exec_driver_sql('DROP TABLE notification_new')
                else:
                    connection.exec_driver_sql('ALTER TABLE notification_new RENAME TO notification')
        notification_columns = {column['name']: column for column in inspect(db.engine).get_columns('notification')}
        if ('post_id' not in notification_columns or 'message' not in notification_columns
                or notification_columns.get('friendship_id', {}).get('nullable') is False):
            # Existing databases predate post notifications; rebuild this small table so
            # friendship_id can be empty while preserving existing friend notifications.
            if db.engine.dialect.name == 'sqlite':
                db.session.commit()
                raw_connection = db.engine.raw_connection()
                try:
                    cursor = raw_connection.cursor()
                    cursor.execute('PRAGMA foreign_keys=OFF')
                    cursor.execute('DROP TABLE IF EXISTS notification_new')
                    cursor.execute('''
                        CREATE TABLE notification_new (
                            id INTEGER NOT NULL PRIMARY KEY,
                            recipient_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
                            actor_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
                            friendship_id INTEGER REFERENCES friendship(id) ON DELETE CASCADE,
                            post_id INTEGER REFERENCES post(id) ON DELETE CASCADE,
                            message TEXT,
                            type VARCHAR(40) NOT NULL DEFAULT 'friend_request',
                            is_read BOOLEAN NOT NULL DEFAULT 0,
                            created_at DATETIME NOT NULL,
                            CONSTRAINT unique_friend_request_notification UNIQUE (friendship_id, recipient_id, type)
                        )
                    ''')
                    old_columns = set(notification_columns)
                    post_expr = 'post_id' if 'post_id' in old_columns else 'NULL'
                    message_expr = 'message' if 'message' in old_columns else 'NULL'
                    cursor.execute(f'''INSERT INTO notification_new
                        (id, recipient_id, actor_id, friendship_id, post_id, message, type, is_read, created_at)
                        SELECT id, recipient_id, actor_id, friendship_id, {post_expr}, {message_expr}, type, is_read, created_at FROM notification''')
                    cursor.execute('DROP TABLE notification')
                    cursor.execute('ALTER TABLE notification_new RENAME TO notification')
                    cursor.execute('CREATE INDEX ix_notification_recipient_id ON notification (recipient_id)')
                    cursor.execute('CREATE INDEX ix_notification_friendship_id ON notification (friendship_id)')
                    cursor.execute('CREATE INDEX ix_notification_post_id ON notification (post_id)')
                    cursor.execute('CREATE INDEX ix_notification_is_read ON notification (is_read)')
                    cursor.execute('CREATE INDEX ix_notification_created_at ON notification (created_at)')
                    raw_connection.commit()
                except Exception:
                    raw_connection.rollback()
                    raise
                finally:
                    try:
                        cursor.execute('PRAGMA foreign_keys=ON')
                    finally:
                        raw_connection.close()
            else:
                raise RuntimeError('Notification schema migration is currently supported only for SQLite.')
            schema_changed = False
        if schema_changed:
            db.session.commit()
        else:
            db.session.rollback()

    # 블루프린트 임포트 및 등록
    from story.views import auth_views, dmviews, main_views, post_views, story_views
    from .views.Reels_views import reels_bp

    app.register_blueprint(reels_bp)
    app.register_blueprint(main_views.bp)
    app.register_blueprint(dmviews.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(post_views.bp)
    app.register_blueprint(story_views.bp)

    account_maintenance = {'last_run': datetime.min}

    # 로그인과 회원가입, 정적 파일만 비로그인 상태에서 접근할 수 있다.
    @app.before_request
    def require_login():
        from flask import request

        # Run account lifecycle maintenance on requests, so no external scheduler is
        # required. Deletion happens on the first request after the 10-day deadline.
        from story.models import User
        from story import db
        now = utc_now_naive()
        # Avoid writing to SQLite on every request. Lifecycle sweeps run at most
        # every 30 minutes; login separately enforces an expired deletion deadline.
        if now - account_maintenance['last_run'] >= timedelta(minutes=30):
            User.query.filter(
                User.status == 'active',
                User.last_activity_at < now - timedelta(days=30)
            ).update({User.status: 'inactive'}, synchronize_session=False)

            expired_users = User.query.filter(
                User.status == 'deletion_pending',
                User.deletion_requested_at <= now - timedelta(days=10)
            ).all()
            if expired_users:
                from story.views.auth_views import permanently_delete_user
                for expired_user in expired_users:
                    permanently_delete_user(expired_user)
            db.session.commit()
            account_maintenance['last_run'] = now

        # Keep the currently logged-in account's activity timestamp current.
        user_id = session.get('user_id')
        if user_id:
            g.user = User.query.get(user_id)
            if g.user and g.user.status == 'active' and (
                not g.user.last_activity_at or
                g.user.last_activity_at < now - timedelta(minutes=5)
            ):
                g.user.last_activity_at = now
                db.session.commit()

        if request.endpoint == 'static' or request.endpoint in {
            'auth.login', 'auth.signup', 'auth.find_info', 'auth.check_signup_value'
        }:
            return None

        if not current_user.is_authenticated or (g.user and g.user.status != 'active'):
            return redirect(url_for('auth.login', next=request.url))

    # 템플릿 필터 (작성 시간)
    @app.template_filter('time_ago')
    def time_ago_filter(value):
        if not value:
            return ""

        diff = as_utc(utc_now_naive()) - as_utc(value)
        seconds = diff.total_seconds()
        minutes = int(seconds // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)

        if minutes < 1:
            return "방금 전"
        elif minutes < 60:
            return f"{minutes}분 전"
        elif hours < 24:
            return f"{hours}시간 전"
        else:
            return f"{days}일 전"

    @app.template_filter('time_ago_local')
    def time_ago_local_filter(value):
        """Story timestamps predate UTC normalization and are naive KST."""
        if not value:
            return ""
        diff = kst_now_naive() - value
        seconds = diff.total_seconds()
        minutes = int(seconds // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)
        if minutes < 1:
            return "방금 전"
        if minutes < 60:
            return f"{minutes}분 전"
        if hours < 24:
            return f"{hours}시간 전"
        return f"{days}일 전"

    @app.template_filter('kst_datetime')
    def kst_datetime_filter(value, fmt='%Y-%m-%d %H:%M'):
        return format_kst(value, fmt)

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
