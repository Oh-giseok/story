from flask import Blueprint, render_template, session, g
from flask_login import current_user
from story import db
from story.models import Post, Story, User
from story.views import dmviews

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    # 1. 로그인 유저 ID 확인 (Flask-Login 및 세션 안전 대응)
    current_uid = None
    if current_user.is_authenticated:
        current_uid = current_user.id
    elif hasattr(g, 'user') and g.user and getattr(g.user, 'id', None):
        current_uid = g.user.id
    elif 'user_id' in session:
        current_uid = session['user_id']

    # 2. 최근 대화 목록 조회 (메시지 페이지와 동일한 dmviews 함수 사용으로 완벽 동기화)
    active_chat_users = []
    if current_uid:
        try:
            if hasattr(dmviews, 'get_active_chat_users'):
                active_chat_users = dmviews.get_active_chat_users(current_uid)
        except Exception as e:
            print(f"[DM Query Error in main_views.py]: {e}")

    # 3. 스토리 및 게시글 데이터 조회
    stories = []
    try:
        stories = Story.query.order_by(Story.id.desc()).all()
    except Exception:
        pass

    posts = []
    try:
        posts = Post.query.order_by(Post.id.desc()).all()
    except Exception:
        pass

    return render_template(
        'index.html',
        posts=posts,
        stories=stories,
        active_chat_users=active_chat_users
    )
    return redirect(url_for('story_list'))
