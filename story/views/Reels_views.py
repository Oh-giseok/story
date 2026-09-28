import os
import cv2
import uuid

from flask import Blueprint, render_template, send_from_directory, redirect, url_for, session
from ..models import Reels, Comments, Reels_Likes
from ..forms import ReelsForm, CommentsForm , ReelsEditForm
from flask import current_app as currunt_app
from .. import db

def get_video_duration(video_path):
    video = cv2.VideoCapture(video_path)

    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)

    video.release()
    return frame_count / fps

reels_bp = Blueprint('reels', __name__ , url_prefix='/reels')

@reels_bp.route('/') #릴스 메인
def reels():
    reels = Reels.query.all()
    comments = Comments.query.all()
    likes = Reels_Likes.query.all()
    form = CommentsForm()


    return render_template(
        'reels/reels.html',
        reels=reels,
        comments=comments,
        likes=likes,
        form=form
    )

@reels_bp.route('/upload', methods = ['GET', 'POST']) #릴스 생성
def upload():
    form = ReelsForm()

    if form.validate_on_submit():
        video = form.video_url.data

        video_filename = f"{uuid.uuid4().hex}_{video.filename}"

        video_path = os.path.join(
            currunt_app.config['UPLOAD_FOLDER'],
            'videos',
            video_filename
        )

        video.save(video_path)


        duration = get_video_duration(video_path)
        print(duration)

        thumbnail = form.thumbnail.data
        thumbnail_filename = f"{uuid.uuid4().hex}_{thumbnail.filename}"
        thumbnail_path = os.path.join(
            currunt_app.config['UPLOAD_FOLDER'],
            'thumbnails',
            thumbnail_filename
        )

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

    return render_template('reels/reels_upload.html', form=form)

@reels_bp.route('/<int:reel_id>/edit', methods=['GET', 'POST'])  #릴스 수정
def edit_reel(reel_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    reel = Reels.query.get_or_404(reel_id)

    if reel.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    form = ReelsEditForm(obj=reel)

    print("폼 검증 결과:", form.validate())
    print("폼 오류:", form.errors)

    if form.validate_on_submit():


        reel.caption = form.caption.data

        # 영상 수정
        if form.video_url.data:
            video = form.video_url.data

            old_video_path = reel.video_url

            video_filename = f"{uuid.uuid4().hex}_{video.filename}"

            video_path = os.path.join(
                currunt_app.config['UPLOAD_FOLDER'],
                'videos',
                video_filename
            )
            video.save(video_path)
            reel.video_url = video_path
            reel.duration = get_video_duration(video_path)

            # 기존 영상이 다른 릴스에서 사용되지 않는 경우 삭제
            video_used = Reels.query.filter(
                Reels.video_url == old_video_path,
                Reels.id != reel.id
            ).first()

            if not video_used:
                if old_video_path and os.path.exists(old_video_path):
                    os.remove(old_video_path)

            # 썸네일 수정
        if form.thumbnail.data:
            thumbnail = form.thumbnail.data

            old_thumbnail_path = reel.thumbnail_url

            thumbnail_filename = f"{uuid.uuid4().hex}_{thumbnail.filename}"

            thumbnail_path = os.path.join(
                currunt_app.config['UPLOAD_FOLDER'],
                'thumbnails',
                thumbnail_filename
            )

            thumbnail.save(thumbnail_path)

            reel.thumbnail_url = thumbnail_path

            # 기존 썸네일이 다른 릴스에서 사용되지 않는 경우 삭제
            thumbnail_used = Reels.query.filter(
                Reels.thumbnail_url == old_thumbnail_path,
                Reels.id != reel.id
            ).first()

            if not thumbnail_used:
                if old_thumbnail_path and os.path.exists(old_thumbnail_path):
                    os.remove(old_thumbnail_path)

        db.session.commit()

        return redirect(url_for('reels.reels'))

    return render_template(
        'reels/reels_edit.html',
        reel=reel,
        form=form
    )


@reels_bp.route('/<int:reel_id>/delete', methods=['POST'])
def delete_reel(reel_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    reel = Reels.query.get_or_404(reel_id)

    # 본인이 올린 릴스만 삭제 가능
    if reel.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    video_path = reel.video_url
    thumbnail_path = reel.thumbnail_url

    # 관련 좋아요 삭제
    Reels_Likes.query.filter_by(reel_id=reel.id).delete()

    # 관련 댓글 삭제
    Comments.query.filter_by(reel_id=reel.id).delete()

    # 릴스 DB 삭제
    db.session.delete(reel)
    db.session.commit()

    # 다른 릴스에서 사용하고 있지 않은 경우에만 실제 파일 삭제
    video_used = Reels.query.filter_by(video_url=video_path).first()
    if not video_used:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

    thumbnail_used = Reels.query.filter_by(thumbnail_url=thumbnail_path).first()
    if not thumbnail_used:
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    return redirect(url_for('reels.reels'))


@reels_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_folder = currunt_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)

@reels_bp.route('/<int:reel_id>/comment',methods = ['GET', 'POST'])
def add_comment(reel_id):
    if 'user_id' not in session:
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

    return redirect(url_for('reels.reels'))

@reels_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    comment = Comments.query.get_or_404(comment_id)

    if comment.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    db.session.delete(comment)
    db.session.commit()

    return redirect(url_for('reels.reels'))

@reels_bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    comment = Comments.query.get_or_404(comment_id)

    if comment.user_id != session['user_id']:
        return redirect(url_for('reels.reels'))

    form = CommentsForm()

    if form.validate_on_submit():
        comment.content = form.content.data
        db.session.commit()

    return redirect(url_for('reels.reels'))


@reels_bp.route('/<int:reel_id>/like', methods=['POST'])
def like_reel(reel_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    like = Reels_Likes.query.filter_by(reel_id=reel_id, user_id = session['user_id']).first()

    if like:
        db.session.delete(like)
    else:
        like = Reels_Likes(reel_id=reel_id, user_id=session['user_id'])
        db.session.add(like)
    db.session.commit()
    return redirect(url_for('reels.reels'))





