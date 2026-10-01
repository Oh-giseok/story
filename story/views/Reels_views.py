import os
import cv2
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    send_from_directory,
    redirect,
    url_for,
    session,
    jsonify,
    request,
    g
)
from flask_login import current_user
from werkzeug.utils import secure_filename
from flask import current_app as currunt_app

from ..models import Reels, Comments, Reels_Likes, User
from ..forms import ReelsForm, CommentsForm, ReelsEditForm
from .. import db
from story.views import dmviews

reels_bp = Blueprint(
    'reels',
    __name__,
    url_prefix='/reels'
)


def get_video_duration(video_path):
    video = cv2.VideoCapture(video_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    video.release()
    return frame_count / fps if fps else 0


# =========================================================
# 릴스 메인
# =========================================================

@reels_bp.route('/')
def reels():
    # Keep the Reels endpoint protected even if the app-wide auth hook changes.
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.url))

    # 1. 로그인 유저 ID 확인 (Flask-Login 및 세션 안전 대응)
    current_uid = None
    if current_user.is_authenticated:
        current_uid = current_user.id
    elif hasattr(g, 'user') and g.user and getattr(g.user, 'id', None):
        current_uid = g.user.id
    elif 'user_id' in session:
        current_uid = session['user_id']

    # 2. 최근 대화 목록 조회 (메시지 페이지 및 main_views와 동일한 dmviews 함수 사용)
    active_chat_users = []
    if current_uid:
        try:
            if hasattr(dmviews, 'get_active_chat_users'):
                active_chat_users = dmviews.get_active_chat_users(current_uid)
        except Exception as e:
            print(f"[DM Query Error in Reels_views.py]: {e}")

    reels = Reels.query.order_by(Reels.created_at.desc()).all()
    comments = Comments.query.all()

    comments_by_reel = {}
    for comment in comments:
        if comment.reel_id not in comments_by_reel:
            comments_by_reel[comment.reel_id] = []
        comments_by_reel[comment.reel_id].append(comment)

    user_id = session.get('user_id')

    like_counts = {}
    liked_reels = set()
    all_likes = Reels_Likes.query.all()

    for like in all_likes:
        like_counts[like.reel_id] = (
            like_counts.get(like.reel_id, 0) + 1
        )

    if user_id:
        for like in all_likes:
            if like.user_id == user_id:
                liked_reels.add(like.reel_id)

    form = CommentsForm()

    return render_template(
        'reels/reels.html',
        reels=reels,
        comments_by_reel=comments_by_reel,
        like_counts=like_counts,
        liked_reels=liked_reels,
        form=form,
        users={u.id: u for u in User.query.all()},
        current_user_id=user_id,
        active_chat_users=active_chat_users  # 👈 최근 대화 목록 전달 추가
    )


# =========================================================
# 릴스 업로드
# =========================================================

@reels_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    form = ReelsForm()

    if form.validate_on_submit():
        video = form.video_url.data

        videos_folder = os.path.join(currunt_app.config['UPLOAD_FOLDER'], 'videos')
        os.makedirs(videos_folder, exist_ok=True)
        video_filename = f"{uuid.uuid4().hex}_{secure_filename(video.filename)}"
        video_path = os.path.join(videos_folder, video_filename)

        video.save(video_path)
        duration = get_video_duration(video_path)

        thumbnail = form.thumbnail.data
        thumbnails_folder = os.path.join(currunt_app.config['UPLOAD_FOLDER'], 'thumbnails')
        os.makedirs(thumbnails_folder, exist_ok=True)
        thumbnail_filename = f"{uuid.uuid4().hex}_{secure_filename(thumbnail.filename)}"
        thumbnail_path = os.path.join(thumbnails_folder, thumbnail_filename)

        thumbnail.save(thumbnail_path)

        reel = Reels(
            user_id=session['user_id'],
            video_url=video_path,
            thumbnail_url=thumbnail_path,
            caption=form.caption.data,
            duration=duration
        )

        db.session.add(reel)
        db.session.commit()

        return redirect(url_for('reels.reels'))

    return render_template(
        'reels/reels_upload.html',
        form=form
    )


# =========================================================
# 릴스 수정
# =========================================================

@reels_bp.route('/<int:reel_id>/edit', methods=['GET', 'POST'])
def edit_reel(reel_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    reel = Reels.query.get_or_404(reel_id)

    if reel.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    form = ReelsEditForm(obj=reel)

    if form.validate_on_submit():
        reel.caption = form.caption.data

        if form.video_url.data:
            video = form.video_url.data
            old_video_path = reel.video_url

            video_filename = f"{uuid.uuid4().hex}_{secure_filename(video.filename)}"
            video_path = os.path.join(
                currunt_app.config['UPLOAD_FOLDER'],
                'videos',
                video_filename
            )
            video.save(video_path)

            reel.video_url = video_path
            reel.duration = get_video_duration(video_path)

            video_used = Reels.query.filter(
                Reels.video_url == old_video_path,
                Reels.id != reel.id
            ).first()

            if not video_used and old_video_path and os.path.exists(old_video_path):
                os.remove(old_video_path)

        if form.thumbnail.data:
            thumbnail = form.thumbnail.data
            old_thumbnail_path = reel.thumbnail_url

            thumbnail_filename = f"{uuid.uuid4().hex}_{secure_filename(thumbnail.filename)}"
            thumbnail_path = os.path.join(
                currunt_app.config['UPLOAD_FOLDER'],
                'thumbnails',
                thumbnail_filename
            )
            thumbnail.save(thumbnail_path)

            reel.thumbnail_url = thumbnail_path

            thumbnail_used = Reels.query.filter(
                Reels.thumbnail_url == old_thumbnail_path,
                Reels.id != reel.id
            ).first()

            if not thumbnail_used and old_thumbnail_path and os.path.exists(old_thumbnail_path):
                os.remove(old_thumbnail_path)

        db.session.commit()
        return redirect(url_for('reels.reels'))

    return render_template(
        'reels/reels_edit.html',
        reel=reel,
        form=form
    )


@reels_bp.route('/<int:reel_id>/caption', methods=['POST'])
def edit_reel_caption(reel_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    reel = Reels.query.get_or_404(reel_id)
    if reel.user_id != session['user_id']:
        return jsonify({'success': False, 'message': '수정 권한이 없습니다.'}), 403

    reel.caption = request.form.get('caption', '')
    db.session.commit()
    return jsonify({'success': True, 'caption': reel.caption})


# =========================================================
# 릴스 삭제
# =========================================================

@reels_bp.route('/<int:reel_id>/delete', methods=['POST'])
def delete_reel(reel_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    reel = Reels.query.get_or_404(reel_id)

    if reel.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    video_path = reel.video_url
    thumbnail_path = reel.thumbnail_url

    Reels_Likes.query.filter_by(reel_id=reel.id).delete()
    Comments.query.filter_by(reel_id=reel.id).delete()

    db.session.delete(reel)
    db.session.commit()

    video_used = Reels.query.filter_by(video_url=video_path).first()
    if not video_used and video_path and os.path.exists(video_path):
        os.remove(video_path)

    thumbnail_used = Reels.query.filter_by(thumbnail_url=thumbnail_path).first()
    if not thumbnail_used and thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    return redirect(url_for('reels.reels'))


# =========================================================
# 업로드 파일
# =========================================================

@reels_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_folder = currunt_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)


# =========================================================
# 댓글 생성
# =========================================================

@reels_bp.route('/<int:reel_id>/comment', methods=['GET', 'POST'])
def add_comment(reel_id):
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
        return redirect(url_for('auth.login'))

    form = CommentsForm()

    if form.validate_on_submit():
        comment = Comments(
            reel_id=reel_id,
            user_id=session['user_id'],
            content=form.content.data
        )

        db.session.add(comment)
        db.session.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            user = User.query.get(comment.user_id)
            return jsonify({
                'success': True,
                'comment_id': comment.id,
                'content': comment.content,
                'user_id': comment.user_id,
                'username': user.username if user else '',
                'comment': {
                    'user_name': user.username if user else '',
                    'profile_img_url': url_for('static', filename=user.profile_img_url) if user and user.profile_img_url else '',
                    'content': comment.content,
                },
            })

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '댓글 내용을 입력해주세요.'}), 400

    return redirect(url_for('reels.reels'))


# =========================================================
# 댓글 삭제
# =========================================================

@reels_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    comment = Comments.query.get_or_404(comment_id)

    if comment.user_id != session['user_id']:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'success': True})


# =========================================================
# 좋아요
# =========================================================

@reels_bp.route('/<int:reel_id>/like', methods=['POST'])
def like_reel(reel_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    reel = Reels.query.get_or_404(reel_id)

    like = Reels_Likes.query.filter_by(
        reel_id=reel_id,
        user_id=session['user_id']
    ).first()

    if like:
        db.session.delete(like)
        liked = False
    else:
        like = Reels_Likes(
            reel_id=reel_id,
            user_id=session['user_id']
        )
        db.session.add(like)
        liked = True

    db.session.commit()

    like_count = Reels_Likes.query.filter_by(reel_id=reel_id).count()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count
        })

    return redirect(url_for('reels.detail_reel', reel_id=reel_id))


# =========================================================
# 릴스 상세
# =========================================================

@reels_bp.route('/<int:reel_id>/detail')
def detail_reel(reel_id):
    reel = Reels.query.get_or_404(reel_id)
    comments = Comments.query.filter_by(reel_id=reel.id).all()
    comments_by_reel = {reel.id: comments}

    user_id = session.get('user_id')
    all_likes = Reels_Likes.query.all()

    like_counts = {}
    for like in all_likes:
        like_counts[like.reel_id] = like_counts.get(like.reel_id, 0) + 1

    liked_reels = set()
    if user_id:
        for like in all_likes:
            if like.user_id == user_id:
                liked_reels.add(like.reel_id)

    form = CommentsForm()
    form_edit = ReelsEditForm(obj=reel)

    if request.args.get('fragment') == '1':
        comment_users = {
            user.id: user
            for user in User.query.filter(User.id.in_([comment.user_id for comment in comments])).all()
        }
        return jsonify({
            'id': reel.id,
            'user_id': reel.user_id,
            'username': User.query.get(reel.user_id).username,
            'profile': User.query.get(reel.user_id).profile_img_url,
            'caption': reel.caption,
            'created': reel.created_at.strftime('%Y-%m-%d %H:%M'),
            'video': url_for('reels.uploaded_file', filename='videos/' + os.path.basename(reel.video_url)),
            'thumbnail': url_for('reels.uploaded_file', filename='thumbnails/' + os.path.basename(reel.thumbnail_url)),
            'liked': reel.id in liked_reels,
            'likes': like_counts.get(reel.id, 0),
            'current_user_id': user_id,
            'comments': [{
                'id': c.id,
                'user_id': c.user_id,
                'username': comment_users[c.user_id].username,
                'profile': url_for('static', filename=comment_users[c.user_id].profile_img_url)
                    if comment_users[c.user_id].profile_img_url else '',
                'content': c.content
            } for c in comments],
            'owner': reel.user_id == user_id
        })
    return redirect(url_for('reels.reels') + '#reel-' + str(reel.id))