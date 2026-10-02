import os
from datetime import datetime, timedelta
from collections import defaultdict
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, current_app, g
from werkzeug.utils import secure_filename

from story import db
from story.forms import StoryForm
from story.models import Story
from story.time_utils import kst_now_naive

bp = Blueprint('story', __name__, url_prefix='/story')


def get_unique_story_list():
    now_time = datetime.now()

    all_stories = Story.query.filter(
        Story.expires_at > now_time
    ).order_by(
        Story.create_date.asc()
    ).all()

    story_list = []
    user_ids = set()

    for story in all_stories:
        if story.user_id not in user_ids:
            story_list.append(story)
            user_ids.add(story.user_id)

    story_list.reverse()
    return story_list


# 24시간 필터링 및 중복 제거가 적용된 스토리 목록 조회
@bp.route('/')
def story_list():
    now = datetime.now()
    all_stories = Story.query.filter(
        Story.expires_at > now
    ).order_by(
        Story.create_date.desc()
    ).all()

    story_list = []
    user_ids = set()
    for story in all_stories:
        if story.user_id not in user_ids:
            story_list.append(story)
            user_ids.add(story.user_id)

    return render_template('story/story_list.html', story_list=story_list)

@bp.route('/detail/<int:story_id>/')
def detail(story_id):
    current_story = Story.query.get_or_404(story_id)
    now = datetime.now()

    active_stories = Story.query.filter(
        Story.expires_at > now
    ).order_by(
        Story.create_date.desc()
    ).all()

    user_groups = defaultdict(list)

    for s in active_stories:
        user_groups[s.user_id].append(s)

    ordered_user_ids = []

    for s in active_stories:
        if s.user_id not in ordered_user_ids:
            ordered_user_ids.append(s.user_id)

    user_stories = user_groups[current_story.user_id]
    user_stories.sort(key=lambda x: x.create_date)

    current_user_idx = ordered_user_ids.index(current_story.user_id)
    story = Story.query.get_or_404(story_id)

    if story.expires_at <= kst_now_naive():
        return redirect(url_for('story.story_list'))

    # 현재 유효한 모든 스토리 목록을 가져옵니다 (목록 정렬 기준과 동일하게 세팅)
    now = kst_now_naive()
    active_stories = Story.query.filter(Story.expires_at > now).order_by(Story.create_date.desc()).all()

    prev_story = None

    # 이전 스토리 두 번째 사용자
    prev_story2 = None

    next_story = None

    # 다음 스토리 두 번째 사용자
    next_story2 = None

    if current_user_idx > 0:
        prev_user_id = ordered_user_ids[current_user_idx - 1]
        prev_user_stories = user_groups[prev_user_id]
        prev_user_stories.sort(key=lambda x: x.create_date)
        prev_story = prev_user_stories[0]

    # 현재 사용자보다 두 번째 앞의 사용자 스토리
    if current_user_idx > 1:
        prev_user2_id = ordered_user_ids[current_user_idx - 2]
        prev_user2_stories = user_groups[prev_user2_id]
        prev_user2_stories.sort(key=lambda x: x.create_date)
        prev_story2 = prev_user2_stories[0]

    if current_user_idx < len(ordered_user_ids) - 1:
        next_user_id = ordered_user_ids[current_user_idx + 1]
        next_user_stories = user_groups[next_user_id]
        next_user_stories.sort(key=lambda x: x.create_date)
        next_story = next_user_stories[0]

    # 수정 추가: 현재 사용자보다 두 번째 뒤의 사용자 스토리
    if current_user_idx < len(ordered_user_ids) - 2:
        next_user2_id = ordered_user_ids[current_user_idx + 2]
        next_user2_stories = user_groups[next_user2_id]
        next_user2_stories.sort(key=lambda x: x.create_date)
        next_story2 = next_user2_stories[0]

    return render_template(
        'story/story_detail.html',
        story=current_story,
        user_stories=user_stories,
        prev_story=prev_story,

        #  두 번째 이전 스토리를 HTML로 전달
        prev_story2=prev_story2,

        next_story=next_story,

        # 두 번째 다음 스토리를 HTML로 전달
        next_story2=next_story2
    )


# 스토리 생성/업로드 기능
@bp.route('/create/', methods=['GET', 'POST'])
def story_create():
    form = StoryForm()

    if request.method == 'POST' and form.validate_on_submit():
        image_file = form.image.data
        caption = form.caption.data
        image_path = None

        if image_file:
            today = datetime.now().strftime('%Y%m%d')
            upload_folder = os.path.join(
                current_app.root_path,
                'static/photo',
                today
            )

            # 저장 경로 : 오늘 날짜로 폴더 생성
            today = kst_now_naive().strftime('%Y%m%d')
            upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
            os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)

            image_path = f'photo/{today}/{filename}'

        now = kst_now_naive()
        expires_at = now + timedelta(days=1)
        user_id = g.user.id

        story = Story(
            user_id=user_id,
            media_url=image_path,
            caption=caption,
            create_date=now,
            expires_at=expires_at
        )

        db.session.add(story)
        db.session.commit()

        if request.form.get('return_to') == 'home':
            return redirect(url_for('main.index'))

        return redirect(url_for('story.story_list'))

    return render_template(
        'story/story_form.html',
        form=form
    )


# 스토리 수정
@bp.route('/modify/<int:story_id>/', methods=['GET', 'POST'])
def modify(story_id):
    story = Story.query.get_or_404(story_id)
    form = StoryForm()

    if story.user_id != g.user.id:
        return redirect(url_for('story.story_list'))

    if request.method == 'POST' and form.validate_on_submit():
        image_file = form.image.data

        if image_file:
            today = datetime.now().strftime('%Y%m%d')
            upload_folder = os.path.join(
                current_app.root_path,
                'static/photo',
                today
            )

            today = kst_now_naive().strftime('%Y%m%d')
            upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
            os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)

            story.media_url = f'photo/{today}/{filename}'

        story.caption = form.caption.data
        db.session.commit()

        return redirect(
            url_for('story.detail', story_id=story.id)
        )

    if request.method == 'GET':
        form.caption.data = story.caption

    return render_template(
        'story/story_form.html',
        form=form,
        story=story
    )


# 스토리 삭제
@bp.route('/delete/<int:story_id>/')
def delete(story_id):
    story = Story.query.get_or_404(story_id)

    if story.user_id != g.user.id:
        return redirect(url_for('story.story_list'))

    db.session.delete(story)
    db.session.commit()

    return redirect(url_for('story.story_list'))