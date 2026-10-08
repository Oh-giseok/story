import os
from datetime import timedelta
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, current_app, g, jsonify, flash

from story import db
from story.forms import StoryForm
from story.models import Story
from story.time_utils import kst_now_naive
from story.media_storage import upload_media

bp = Blueprint('story', __name__, url_prefix='/story')


def _active_story_groups():
    active_stories = Story.query.filter(
        Story.expires_at > kst_now_naive()
    ).order_by(Story.create_date.desc(), Story.id.desc()).all()
    groups = defaultdict(list)
    ordered_user_ids = []
    for item in active_stories:
        if item.user_id not in groups:
            ordered_user_ids.append(item.user_id)
        groups[item.user_id].append(item)
    for items in groups.values():
        items.sort(key=lambda item: (item.create_date, item.id))
    return groups, ordered_user_ids


def _story_payload(item):
    is_owner = bool(g.user and g.user.id == item.user_id)
    return {
        'id': item.id,
        'user_id': item.user_id,
        'media_url': url_for('static', filename=item.media_url),
        'caption': item.caption or '',
        'created_label': current_app.jinja_env.filters['time_ago_local'](item.create_date),
        'is_owner': is_owner,
        'modify_url': url_for('story.modify', story_id=item.id),
        'delete_url': url_for('story.delete', story_id=item.id),
        'username': item.user.username,
        'profile_url': url_for('static', filename=item.user.profile_img_url) if item.user.profile_img_url else None,
        'profile_page_url': url_for('auth.mypage', user_id=item.user_id),
        'stories': [{
            'id': story.id,
            'media_url': url_for('static', filename=story.media_url),
            'caption': story.caption or '',
            'created_label': current_app.jinja_env.filters['time_ago_local'](story.create_date),
            'is_owner': is_owner,
            'modify_url': url_for('story.modify', story_id=story.id),
            'delete_url': url_for('story.delete', story_id=story.id),
            'username': story.user.username,
            'profile_url': url_for('static', filename=story.user.profile_img_url) if story.user.profile_img_url else None,
            'profile_page_url': url_for('auth.mypage', user_id=story.user_id),
        } for story in Story.query.filter(
            Story.user_id == item.user_id,
            Story.expires_at > kst_now_naive()
        ).order_by(Story.create_date.asc(), Story.id.asc()).all()]
    }


def _adjacent_story_payload(item):
    if not item:
        return None
    return {
        'id': item.id,
        'detail_url': url_for('story.detail', story_id=item.id),
        'media_url': url_for('static', filename=item.media_url),
        'is_video': item.media_url.lower().endswith(('.mp4', '.webm', '.ogg', '.mov')),
        'username': item.user.username,
        'profile_url': url_for('static', filename=item.user.profile_img_url) if item.user.profile_img_url else None,
        'created_label': current_app.jinja_env.filters['time_ago_local'](item.create_date),
    }


@bp.route('/api/detail/<int:story_id>/')
def detail_data(story_id):
    """Return an active story's user group for in-place viewer transitions."""
    groups, ordered_user_ids = _active_story_groups()
    item = Story.query.get_or_404(story_id)
    if item.expires_at <= kst_now_naive() or item.user_id not in groups:
        return jsonify({'error': 'story_expired'}), 404
    user_index = ordered_user_ids.index(item.user_id)
    payload = _story_payload(item)
    payload['user_stories'] = payload.pop('stories')
    payload['next_story_id'] = groups[ordered_user_ids[user_index + 1]][0].id if user_index + 1 < len(ordered_user_ids) else None
    payload['previous_story_id'] = groups[ordered_user_ids[user_index - 1]][-1].id if user_index > 0 else None
    payload['adjacent'] = {
        'prev_story': _adjacent_story_payload(groups[ordered_user_ids[user_index - 1]][-1]) if user_index > 0 else None,
        'prev_story2': _adjacent_story_payload(groups[ordered_user_ids[user_index - 2]][-1]) if user_index > 1 else None,
        'next_story': _adjacent_story_payload(groups[ordered_user_ids[user_index + 1]][0]) if user_index + 1 < len(ordered_user_ids) else None,
        'next_story2': _adjacent_story_payload(groups[ordered_user_ids[user_index + 2]][0]) if user_index + 2 < len(ordered_user_ids) else None,
    }
    return jsonify(payload)


def get_unique_story_list():
    groups, ordered_user_ids = _active_story_groups()
    # Keep one ring per user, linking to that user's first active Story.
    return [groups[user_id][0] for user_id in ordered_user_ids]


# 24시간 필터링 및 중복 제거가 적용된 스토리 목록 조회
@bp.route('/')
def story_list():
    return render_template('story/story_list.html', story_list=get_unique_story_list())

@bp.route('/detail/<int:story_id>/')
def detail(story_id):
    current_story = Story.query.get_or_404(story_id)
    user_groups, ordered_user_ids = _active_story_groups()
    if current_story.expires_at <= kst_now_naive() or current_story.user_id not in user_groups:
        return redirect(url_for('story.story_list'))

    user_stories = user_groups[current_story.user_id]

    current_user_idx = ordered_user_ids.index(current_story.user_id)
    story = current_story

    prev_story = None

    # 이전 스토리 두 번째 사용자
    prev_story2 = None

    next_story = None

    # 다음 스토리 두 번째 사용자
    next_story2 = None

    if current_user_idx > 0:
        prev_user_id = ordered_user_ids[current_user_idx - 1]
        prev_user_stories = user_groups[prev_user_id]
        prev_user_stories.sort(key=lambda x: (x.create_date, x.id))
        prev_story = prev_user_stories[-1]

    # 현재 사용자보다 두 번째 앞의 사용자 스토리
    if current_user_idx > 1:
        prev_user2_id = ordered_user_ids[current_user_idx - 2]
        prev_user2_stories = user_groups[prev_user2_id]
        prev_user2_stories.sort(key=lambda x: (x.create_date, x.id))
        prev_story2 = prev_user2_stories[-1]

    if current_user_idx < len(ordered_user_ids) - 1:
        next_user_id = ordered_user_ids[current_user_idx + 1]
        next_user_stories = user_groups[next_user_id]
        next_user_stories.sort(key=lambda x: (x.create_date, x.id))
        next_story = next_user_stories[0]

    # 수정 추가: 현재 사용자보다 두 번째 뒤의 사용자 스토리
    if current_user_idx < len(ordered_user_ids) - 2:
        next_user2_id = ordered_user_ids[current_user_idx + 2]
        next_user2_stories = user_groups[next_user2_id]
        next_user2_stories.sort(key=lambda x: (x.create_date, x.id))
        next_story2 = next_user2_stories[0]

    return render_template(
        'story/story_detail.html',
        story=current_story,
        user_stories=user_stories,
        prev_story=prev_story,

        prev_story2=prev_story2,
        next_story=next_story,
        next_story2=next_story2
    )


# 스토리 생성/업로드 기능
@bp.route('/create/', methods=['GET', 'POST'])
def story_create():
    form = StoryForm()

    if request.method == 'GET':
        return redirect(url_for('main.index'))

    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error)
        if not form.errors:
            flash('스토리를 등록할 수 없습니다. 다시 시도해 주세요.')
        if request.form.get('return_to') == 'home':
            return redirect(url_for('main.index'))
        return redirect(url_for('story.story_list'))

    if request.method == 'POST':
        image_file = form.image.data
        caption = form.caption.data
        image_path = None

        if image_file:
            image_path = upload_media(image_file, 'story-posts', resource_type='image')

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

    return redirect(url_for('main.index'))


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
            story.media_url = upload_media(image_file, 'story-posts', resource_type='image')

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

    return redirect(url_for('main.index'))
