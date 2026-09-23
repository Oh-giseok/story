from flask import Flask, render_template
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    migrate = Migrate()


    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    migrate.init_app(app, db)
    from story import models

    @app.route('/')
    def index():
        return "flaks team project"

    @app.route('/story/')
    def story_list():
        # 1. 지금 현재 시간을 구합니다.
        now = datetime.now()

        # 2. 만료 시간(expires_at)이 현재 시간보다 미래인(남아있는) 스토리만 가져옵니다!
        story_list = models.Story.query.filter(models.Story.expires_at > now).order_by(
            models.Story.create_date.desc()).all()
        return render_template('story/story_list.html', story_list=story_list)

    @app.template_filter('time_ago')
    def time_ago_filter(value):
        if not value:
            return ""

        diff = datetime.now() - value

        seconds = diff.total_seconds()
        minutes = int(seconds // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)

        # 시간 차이에 따라 다르게 글씨를 내보냅니다
        if minutes < 1:
            return "방금 전"
        elif minutes < 60:
            return f"{minutes}분 전"
        elif hours < 24:
            return f"{hours}시간"  # 인스타 스타일: '16시간' 형태로 출력
        else:
            return f"{days}일 전"

    return app