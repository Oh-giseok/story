import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename

from story import db
from story.models import Story


bp = Blueprint('story', __name__, url_prefix='/story')

#  24시간 필터링이 적용된 스토리 목록 조회
@bp.route('/')
def story_list():
    now = datetime.now()
    story_list = Story.query.filter(Story.expires_at > now).order_by(Story.create_date.desc()).all()
    return render_template('story/story_list.html', story_list=story_list)


# 스토리 생성/업로드 기능 (배우신 이미지 저장 로직 반영!)
@bp.route('/create/', methods=['GET', 'POST'])
# @login_required
def create():
    if request.method == 'POST':
        # 폼에서 전송된 이미지 파일 가져오기
        image_file = request.files.get('image')
        caption = request.form.get('caption', '')
        image_path = None

        if image_file:
            # 저장 경로 : 오늘 날짜로 폴더 생성
            today = datetime.now().strftime('%Y%m%d')
            upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
            os.makedirs(upload_folder, exist_ok=True)

            # 파일 저장
            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)

            # DB에 저장할 상대 경로 계산
            image_path = f'photo/{today}/{filename}'

        now = datetime.now()
        expires_at = now + timedelta(days=1)

        user_id = 1

        story = Story(
            user_id=user_id,
            media_url=image_path,  # 저장된 이미지 경로 기록
            caption=caption,
            create_date=now,
            expires_at=expires_at  # 24시간 제한 칼럼 세팅!
        )
        db.session.add(story)
        db.session.commit()

        return redirect(url_for('story.story_list'))

    return render_template('story/story_form.html')
