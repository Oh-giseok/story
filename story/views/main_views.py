import datetime

from flask import Blueprint, render_template, session, g, request
from flask_login import current_user
from sqlalchemy import or_
from story.models import Post, PostRepost, Reels, Story, User
from story.time_utils import kst_now_naive
from story.views import dmviews

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    current_uid = None
    if current_user.is_authenticated:
        current_uid = current_user.id
    elif hasattr(g, 'user') and g.user and getattr(g.user, 'id', None):
        current_uid = g.user.id
    elif 'user_id' in session:
        current_uid = session['user_id']
    active_chat_users = []
    if current_uid:
        try:
            if hasattr(dmviews, 'get_active_chat_users'):
                active_chat_users = dmviews.get_active_chat_users(current_uid)
        except Exception as e:
            print(f"[DM Query Error in main_views.py]: {e}")
    stories = []
    try:
        now_time = datetime.now()
        all_stories = Story.query.filter(
            Story.expires_at > now_time
        ).order_by(
            Story.create_date.asc()
        ).all()

        user_ids = set()
        for story in all_stories:
            if story.user_id not in user_ids:
                stories.append(story)
                user_ids.add(story.user_id)

        stories.reverse()
    except Exception as e:
        print(f"[Story Query Error]: {e}")

    posts = []
    reposted_post_ids = set()
    try:
        posts = Post.query.order_by(Post.id.desc()).all()
        if current_uid:
            reposted_post_ids = {
                repost.post_id
                for repost in PostRepost.query.filter_by(user_id=current_uid).all()
            }
    except Exception:
        pass
    return render_template(
        'post/post_list.html',
        posts=posts,
        reposted_post_ids=reposted_post_ids,
        story_list=stories,
        active_chat_users=active_chat_users
    )

@bp.route('/search')
def search():
    current_uid = None
    if current_user.is_authenticated:
        current_uid = current_user.id
    elif hasattr(g, 'user') and g.user and getattr(g.user, 'id', None):
        current_uid = g.user.id
    elif 'user_id' in session:
        current_uid = session['user_id']

    active_chat_users = []
    if current_uid:
        try:
            if hasattr(dmviews, 'get_active_chat_users'):
                active_chat_users = dmviews.get_active_chat_users(current_uid)
        except Exception as e:
            print(f"[DM Query Error in search]: {e}")
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
        reel_users=reel_users,
        active_chat_users=active_chat_users
    )
