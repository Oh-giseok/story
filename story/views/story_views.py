import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, current_app, g
from werkzeug.utils import secure_filename

from story import db
from story.forms import StoryForm
from story.models import Story

bp = Blueprint('story', __name__, url_prefix='/story')


# 24시간 필터링이 적용된 스토리 목록 조회
@bp.route('/')
def story_list():
    now = datetime.now()

    # 🌟 [진짜 해결책] 과거순(asc)으로 먼저 전체 스토리를 모아야 유저가 올린 '첫 번째 스토리(5번)'가 리스트 상단에 오게 됩니다.
    all_stories = Story.query.filter(
        Story.expires_at > now
    ).order_by(
        Story.create_date.asc()
    ).all()

    story_list = []
    user_ids = set()

    for story in all_stories:
        if story.user_id not in user_ids:
            story_list.append(story)
            user_ids.add(story.user_id) # 유저당 가장 먼저 올린 '첫 번째 글'만 고유하게 선점

    # 🌟 하지만 화면에는 최신 글을 가진 유저가 맨 왼쪽에 오도록 리스트 전체 순서만 역순으로 싹 뒤집어줍니다!
    story_list.reverse()

    return render_template('story/story_list.html', story_list=story_list)


@bp.route('/detail/<int:story_id>/')
def detail(story_id):
    current_story = Story.query.get_or_404(story_id)
    now = datetime.now()

    # 1. 메인 목록 화면과 동일하게 전체 스토리를 '최신순(desc)'으로 1차 정렬합니다.
    active_stories = Story.query.filter(Story.expires_at > now).order_by(Story.create_date.desc()).all()

    # 2. 모든 유효한 스토리를 유저별로 그룹화하여 묶어줍니다.
    from collections import defaultdict
    user_groups = defaultdict(list)
    for s in active_stories:
        user_groups[s.user_id].append(s)

    # 3. 메인 목록에 뜨는 고유 유저 아이디 순서(최신순 배치 순서)를 추려냅니다.
    ordered_user_ids = []
    for s in active_stories:
        if s.user_id not in ordered_user_ids:
            ordered_user_ids.append(s.user_id)

    # 4. 현재 스토리를 올린 주인의 모든 스토리 리스트 배열을 확보합니다.
    user_stories = user_groups[current_story.user_id]
    user_stories.sort(key=lambda x: x.create_date)

    current_user_idx = ordered_user_ids.index(current_story.user_id)

    prev_story = None
    next_story = None

    # 5. 🌟 [정밀 교정 수식] 최신순 목록 순서(ordered_user_ids) 흐름과 완벽히 동기화합니다.
    # 인스타 정렬 기준: 인덱스가 커질수록(오른쪽으로 갈수록) 예전 유저 글입니다.

    # 🟢 내 기준 왼쪽(이전 유저 카드): 최신순 목록상 나보다 왼쪽에 있던(인덱스가 작은) 유저의 스토리
    if current_user_idx > 0:
        prev_user_id = ordered_user_ids[current_user_idx - 1]
        prev_user_stories = user_groups[prev_user_id]
        prev_user_stories.sort(key=lambda x: x.create_date)
        prev_story = prev_user_stories[0]  # 그 유저의 첫 번째 조각 객체 대입

    # 🟢 내 기준 오른쪽(다음 유저 카드): 최신순 목록상 나보다 오른쪽에 배치된(인덱스가 큰) 유저의 스토리
    if current_user_idx < len(ordered_user_ids) - 1:
        next_user_id = ordered_user_ids[current_user_idx + 1]
        next_user_stories = user_groups[next_user_id]
        next_user_stories.sort(key=lambda x: x.create_date)
        next_story = next_user_stories[0]  # 그 유저의 첫 번째 조각 객체 대입

    return render_template(
        'story/story_detail.html',
        story=current_story,
        user_stories=user_stories,
        prev_story=prev_story,
        next_story=next_story
    )

# 스토리 생성/업로드 기능 (배우신 이미지 저장 로직 반영!)
@bp.route('/create/', methods=['GET', 'POST'])
def story_create():
    form = StoryForm()
    if request.method == 'POST' and form.validate_on_submit():
        image_file = form.image.data
        caption = form.caption.data
        image_path = None

        if image_file:
            today = datetime.now().strftime('%Y%m%d')
            upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
            os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)

            image_path = f'photo/{today}/{filename}'

        now = datetime.now()
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

        return redirect(url_for('story.story_list'))

    return render_template('story/story_form.html', form=form)


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
            upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
            os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)

            story.media_url = f'photo/{today}/{filename}'

        story.caption = form.caption.data

        db.session.commit()

        return redirect(url_for('story.detail', story_id=story.id))

    if request.method == 'GET':
        form.caption.data = story.caption

    return render_template('story/story_form.html', form=form, story=story)


# 스토리 삭제
@bp.route('/delete/<int:story_id>/')
def delete(story_id):
    story = Story.query.get_or_404(story_id)

    if story.user_id != g.user.id:
        return redirect(url_for('story.story_list'))

    db.session.delete(story)
    db.session.commit()

    return redirect(url_for('story.story_list'))
