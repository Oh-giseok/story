import os
import cv2

from flask import Blueprint, render_template, send_from_directory, redirect, url_for
from ..models import Reels
from ..forms import ReelsForm
from flask import current_app as currunt_app
from .. import db

def get_video_duration(video_path):
    video = cv2.VideoCapture(video_path)

    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)

    video.release()
    return frame_count / fps

reels_bp = Blueprint('reels', __name__ , url_prefix='/reels')

@reels_bp.route('/')
def reels():
    reels = Reels.query.all()

    return render_template('reels/reels.html', reels = reels)

@reels_bp.route('/upload', methods = ['GET', 'POST'])
def upload():
    form = ReelsForm()

    if form.validate_on_submit():
        video = form.video_url.data

        video_path = os.path.join(currunt_app.config['UPLOAD_FOLDER'], 'videos',video.filename)
        video.save(video_path)
        print("영상저장 성공")

        duration = get_video_duration(video_path)
        print(duration)

        thumbnail = form.thumbnail.data
        thumbnail_path = os.path.join(currunt_app.config['UPLOAD_FOLDER'], 'thumbnails',thumbnail.filename)
        thumbnail.save(thumbnail_path)
        print('썸네일 성공')

        reel = Reels(
            user_id=1,
            video_url=video_path,
            thumbnail_url=thumbnail_path,
            caption=form.caption.data,
            duration=duration
        )

        db.session.add(reel)
        db.session.commit()

        print('DB 저장 성공')

        return redirect(url_for('reels.reels'))

    return render_template('reels/reels_upload.html', form=form)

@reels_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_folder = currunt_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)


