from datetime import datetime
from flask import Blueprint, render_template, session, g, request
from flask_login import current_user
from sqlalchemy import or_
from story.models import Post, Reels, Story, User
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
        stories = Story.query.filter(Story.expires_at > datetime.now()).order_by(Story.create_date.desc()).all()
    except Exception:
        pass

    posts = []
    try:
        posts = Post.query.order_by(Post.id.desc()).all()
    except Exception:
        pass

    return render_template(
        'post/post_list.html',
        posts=posts,
        story_list=stories,
        active_chat_users=active_chat_users
    )

@bp.route('/search')
def search():
    query = request.args.get('q', '').strip()[:100]
    category = request.args.get('type', 'users')
    if category not in {'users', 'posts', 'reels'}:
        category = 'users'

    users = []
    posts = []
    reels = []
    reel_users = {}
    if query:
        pattern = f'%{query}%'
        if category == 'users':
            users = User.query.filter(User.username.ilike(pattern)).order_by(User.username.asc()).limit(60).all()
        elif category == 'posts':
            posts = Post.query.join(User, Post.user_id == User.id).filter(
                or_(Post.caption.ilike(pattern), User.username.ilike(pattern))
            ).order_by(Post.created_at.desc()).limit(60).all()
        else:
            reels = Reels.query.join(User, Reels.user_id == User.id).filter(
                or_(Reels.caption.ilike(pattern), User.username.ilike(pattern))
            ).order_by(Reels.created_at.desc()).limit(60).all()
            reel_users = {
                user.id: user
                for user in User.query.filter(User.id.in_({reel.user_id for reel in reels})).all()
            } if reels else {}

    return render_template(
        'search.html',
        query=query,
        category=category,
        users=users,
        posts=posts,
        reels=reels,
        reel_users=reel_users
    )
