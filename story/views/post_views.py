import os
from datetime import datetime

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from story import db
from story.models import Post, PostLike, User

bp = Blueprint('post', __name__, url_prefix='/post')


@bp.route('/list')
def _list():
    statement = db.select(Post).order_by(Post.created_at.desc())
    posts = db.session.scalars(statement).all()
    return render_template('post/post_list.html', posts=posts)


@bp.route('/create', methods=['POST'])
def _create():
    uploaded_file = request.files.get('media_file')
    if not uploaded_file or not uploaded_file.filename:
        return redirect(url_for('post._list'))

    filename = secure_filename(uploaded_file.filename)
    if not filename:
        return redirect(url_for('post._list'))

    today = datetime.now().strftime('%Y-%m-%d')
    upload_folder = os.path.join(current_app.config['POST_UPLOAD_FOLDER'], today)
    os.makedirs(upload_folder, exist_ok=True)
    uploaded_file.save(os.path.join(upload_folder, filename))

    post = Post()
    post.user_id = 1  # 로그인 연결 전 임시 사용자
    post.caption = request.form.get('caption')
    post.media_url = f'/static/photo/{today}/{filename}'
    db.session.add(post)
    db.session.commit()

    return redirect(url_for('post._list'))


@bp.route('/like/<int:post_id>', methods=['POST'])
def like(post_id):
    user_id = 1  # 로그인 연결 전 임시 사용자
    statement = db.select(PostLike).filter_by(post_id=post_id, user_id=user_id)
    existing_like = db.session.scalar(statement)

    if existing_like:
        db.session.delete(existing_like)
    else:
        if db.session.get(User, user_id) is None:
            return redirect(url_for('post._list'))
        new_like = PostLike()
        new_like.post_id = post_id
        new_like.user_id = user_id
        db.session.add(new_like)

    db.session.commit()
    return redirect(url_for('post._list'))
