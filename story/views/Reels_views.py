import os
import cv2
import uuid

from flask import (
    Blueprint,
    render_template,
    send_from_directory,
    redirect,
    url_for,
    session,
    jsonify,
    request
)

from ..models import Reels, Comments, Reels_Likes, User
from ..forms import ReelsForm, CommentsForm, ReelsEditForm
from flask import current_app as currunt_app
from .. import db
from werkzeug.utils import secure_filename


def get_video_duration(video_path):
    video = cv2.VideoCapture(video_path)

    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)

    video.release()

    return frame_count / fps if fps else 0


reels_bp = Blueprint(
    'reels',
    __name__,
    url_prefix='/reels'
)


# =========================================================
# 릴스 메인
# =========================================================

@reels_bp.route('/')
def reels():
    # Keep the Reels endpoint protected even if the app-wide auth hook changes.
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.url))

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
        current_user_id=user_id
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

        print(duration)

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

        return redirect(
            url_for('reels.reels')
        )

    return render_template(
        'reels/reels_upload.html',
        form=form
    )


# =========================================================
# 릴스 수정
# =========================================================

@reels_bp.route(
    '/<int:reel_id>/edit',
    methods=['GET', 'POST']
)
def edit_reel(reel_id):

    if 'user_id' not in session:
        return redirect(
            url_for('auth.login')
        )

    reel = Reels.query.get_or_404(reel_id)

    if reel.user_id != session['user_id']:
        return redirect(
            url_for('reels.reels')
        )

    form = ReelsEditForm(obj=reel)

    if form.validate_on_submit():

        reel.caption = form.caption.data

        # -------------------------------------------------
        # 영상 수정
        # -------------------------------------------------

        if form.video_url.data:

            video = form.video_url.data

            old_video_path = reel.video_url

            video_filename = (
                f"{uuid.uuid4().hex}_{video.filename}"
            )

            video_path = os.path.join(
                currunt_app.config['UPLOAD_FOLDER'],
                'videos',
                video_filename
            )

            video.save(video_path)

            reel.video_url = video_path

            reel.duration = get_video_duration(
                video_path
            )

            video_used = Reels.query.filter(
                Reels.video_url == old_video_path,
                Reels.id != reel.id
            ).first()

            if not video_used:

                if (
                    old_video_path
                    and os.path.exists(old_video_path)
                ):
                    os.remove(old_video_path)

        # -------------------------------------------------
        # 썸네일 수정
        # -------------------------------------------------

        if form.thumbnail.data:

            thumbnail = form.thumbnail.data

            old_thumbnail_path = reel.thumbnail_url

            thumbnail_filename = (
                f"{uuid.uuid4().hex}_{thumbnail.filename}"
            )

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

            if not thumbnail_used:

                if (
                    old_thumbnail_path
                    and os.path.exists(old_thumbnail_path)
                ):
                    os.remove(old_thumbnail_path)

        db.session.commit()

        return redirect(
            url_for('reels.reels')
        )

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

@reels_bp.route(
    '/<int:reel_id>/delete',
    methods=['POST']
)
def delete_reel(reel_id):

    if 'user_id' not in session:
        return redirect(
            url_for('auth.login')
        )

    reel = Reels.query.get_or_404(reel_id)

    if reel.user_id != session['user_id']:
        return redirect(
            url_for('reels.reels')
        )

    video_path = reel.video_url
    thumbnail_path = reel.thumbnail_url

    # 좋아요 삭제
    Reels_Likes.query.filter_by(
        reel_id=reel.id
    ).delete()

    # 댓글 삭제
    Comments.query.filter_by(
        reel_id=reel.id
    ).delete()

    # 릴스 삭제
    db.session.delete(reel)

    db.session.commit()

    # 다른 릴스에서 사용하지 않는 영상이면 삭제
    video_used = Reels.query.filter_by(
        video_url=video_path
    ).first()

    if not video_used:

        if (
            video_path
            and os.path.exists(video_path)
        ):
            os.remove(video_path)

    # 다른 릴스에서 사용하지 않는 썸네일이면 삭제
    thumbnail_used = Reels.query.filter_by(
        thumbnail_url=thumbnail_path
    ).first()

    if not thumbnail_used:

        if (
            thumbnail_path
            and os.path.exists(thumbnail_path)
        ):
            os.remove(thumbnail_path)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    return redirect(
        url_for('reels.reels')
    )


# =========================================================
# 업로드 파일
# =========================================================

@reels_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):

    upload_folder = (
        currunt_app.config['UPLOAD_FOLDER']
    )

    return send_from_directory(
        upload_folder,
        filename
    )


# =========================================================
# 댓글 생성
# =========================================================

@reels_bp.route('/<int:reel_id>/comment', methods=['GET', 'POST'])
def add_comment(reel_id):
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '로그인이 필요합니다.'
            }), 401

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

        # AJAX 요청이면 JSON으로 응답
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

    # AJAX 요청인데 폼 검증에 실패한 경우
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': False,
            'message': '댓글 내용을 입력해주세요.'
        }), 400

    return redirect(url_for('reels.reels'))


# =========================================================
# 댓글 삭제
# =========================================================

@reels_bp.route(
    '/comment/<int:comment_id>/delete',
    methods=['POST']
)
def delete_comment(comment_id):

    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    comment = Comments.query.get_or_404(
        comment_id
    )

    if comment.user_id != session['user_id']:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'success': True})


# =========================================================
# 좋아요
# =========================================================

@reels_bp.route(
    '/<int:reel_id>/like',
    methods=['POST']
)
def like_reel(reel_id):

    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': '로그인이 필요합니다.'
        }), 401

    reel = Reels.query.get_or_404(reel_id)

    like = Reels_Likes.query.filter_by(
        reel_id=reel_id,
        user_id=session['user_id']
    ).first()

    # 좋아요 취소
    if like:

        db.session.delete(like)

        liked = False

    # 좋아요 추가
    else:

        like = Reels_Likes(
            reel_id=reel_id,
            user_id=session['user_id']
        )

        db.session.add(like)

        liked = True

    db.session.commit()

    # 현재 릴스의 좋아요 개수
    like_count = Reels_Likes.query.filter_by(
        reel_id=reel_id
    ).count()

    # AJAX 요청이면 JSON 반환
    if request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest':

        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count
        })

    # 일반 POST 요청이면 디테일 페이지로 돌아감
    return redirect(
        url_for(
            'reels.detail_reel',
            reel_id=reel_id
        )
    )


# =========================================================
# 릴스 상세
# =========================================================

@reels_bp.route(
    '/<int:reel_id>/detail'
)
def detail_reel(reel_id):

    reel = Reels.query.get_or_404(
        reel_id
    )

    comments = Comments.query.filter_by(
        reel_id=reel.id
    ).all()

    comments_by_reel = {
        reel.id: comments
    }

    user_id = session.get(
        'user_id'
    )

    all_likes = Reels_Likes.query.all()

    like_counts = {}

    for like in all_likes:

        like_counts[like.reel_id] = (
            like_counts.get(
                like.reel_id,
                0
            ) + 1
        )

    liked_reels = set()

    if user_id:

        for like in all_likes:

            if like.user_id == user_id:
                liked_reels.add(
                    like.reel_id
                )

    form = CommentsForm()

    form_edit = ReelsEditForm(
        obj=reel
    )

    if request.args.get('fragment') == '1':
        from ..models import User
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
