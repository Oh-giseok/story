import os
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, session, g, flash
import os
import secrets
from story import db
from story.models import Post, User, PostLike, PostComment, PostRepost, Story, Notification
from story.time_utils import utc_isoformat, kst_now_naive, utc_now_naive
from story.media_storage import create_signed_upload_url, has_image_signature, upload_media, verify_stored_image
from story.views.story_views import get_unique_story_list

# /post 경로로 들어오는 요청들을 처리할 블루프린트 생성
bp = Blueprint('post', __name__, url_prefix='/post')

# 공통 유저 ID 추출 함수 (g.user 또는 session 활용)
def get_current_user_id():
    # 1. g.user 객체가 있는 경우 (Flask 로그인 전처리 공통 객체 사용 시)
    if hasattr(g, 'user') and g.user:
        return g.user.id
    # 2. session에 user_id가 직접 들어있는 경우
    if 'user_id' in session:
        return session['user_id']
    # 3. 예외 상황 처리 (로그인 정보가 없을 때 기본값 지정 혹은 None)
    return None


# 1. 게시물 목록 보기
@bp.route('/')
def _list():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    story_list = get_unique_story_list()
    user_id = session.get('user_id')
    reposted_post_ids = {
        repost.post_id
        for repost in PostRepost.query.filter_by(user_id=user_id).all()
    } if user_id else set()
    liked_post_ids = {
        like.post_id
        for like in PostLike.query.filter_by(user_id=user_id).all()
    } if user_id else set()
    return render_template(
        'post/post_list.html', posts=posts, story_list=story_list,
        reposted_post_ids=reposted_post_ids,
        liked_post_ids=liked_post_ids
    )


@bp.route('/<int:post_id>/detail-data')
def detail_data(post_id):
    post = Post.query.get_or_404(post_id)
    user_id = session.get('user_id')
    comments = PostComment.query.filter_by(post_id=post.id).order_by(
        PostComment.created_at.asc(), PostComment.id.asc()
    ).all()
    return jsonify({
        'id': post.id,
        'user_id': post.user_id,
        'username': post.user.username if post.user else '',
        'profile_img_url': post.user.profile_img_url if post.user else '',
        'caption': post.caption or '',
        'media_url': post.media_url or '',
        'liked': bool(user_id and PostLike.query.filter_by(post_id=post.id, user_id=user_id).first()),
        'like_count': PostLike.query.filter_by(post_id=post.id).count(),
        'comments': [{
            'id': comment.id,
            'user_id': comment.user_id,
            'username': comment.user.username if comment.user else '',
            'profile_img_url': comment.user.profile_img_url if comment.user else '',
            'content': comment.content,
        } for comment in comments],
    })


# 2. 게시물 등록 처리
@bp.route('/create', methods=['GET', 'POST'])
def _create():
    user_id = get_current_user_id()
    if not user_id:
        # 로그인하지 않은 유저인 경우 로그인 페이지 등으로 이동 또는 에러 처리
        return redirect(url_for('auth.login'))  # 사용하시는 로그인 라우트명으로 맞추어 사용해주세요.

    if request.method == 'GET':
        # 게시물 작성 UI는 공통 모달에 있으므로 홈에서 모달을 연다.
        return redirect(url_for('main.index', open_post_composer='1'))

    caption = request.form.get('caption')

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        phase = payload.get('phase')

        if phase == 'sign':
            files = payload.get('files')
            if not isinstance(files, list) or not files or len(files) > 10:
                return jsonify({'error': '게시물 파일은 1개 이상 10개 이하로 선택해주세요.'}), 400

            signed_uploads = []
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            for item in files:
                if not isinstance(item, dict):
                    return jsonify({'error': '잘못된 파일 정보입니다.'}), 400
                filename = os.path.basename(str(item.get('name') or ''))
                extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
                size = item.get('size')
                content_type = str(item.get('type') or '').lower()
                if (extension not in allowed_extensions or not content_type.startswith('image/')
                        or not isinstance(size, int) or isinstance(size, bool) or size <= 0):
                    return jsonify({'error': '이미지 파일만 업로드할 수 있습니다.'}), 400
                object_key = f"{secrets.token_urlsafe(12)}.{extension}"
                signed_upload = create_signed_upload_url(object_key)
                if signed_upload is None:
                    return jsonify({'available': False})
                signed_uploads.append(signed_upload)
            session['pending_post_upload_keys'] = [upload['key'] for upload in signed_uploads]
            return jsonify({'available': True, 'uploads': signed_uploads})

        if phase == 'publish':
            keys = payload.get('keys')
            if not isinstance(keys, list) or not keys or len(keys) > 10:
                return jsonify({'error': '게시물 파일 정보가 올바르지 않습니다.'}), 400
            pending_keys = session.get('pending_post_upload_keys', [])
            if (any(not isinstance(key, str) or '..' in key or '/' in key for key in keys)
                    or keys != pending_keys
                    or any(key.rsplit('.', 1)[-1].lower() not in {'jpg', 'jpeg', 'png', 'gif', 'webp'} for key in keys)):
                return jsonify({'error': '게시물 파일 정보가 올바르지 않습니다.'}), 400
            if not all(verify_stored_image(key) for key in keys):
                session.pop('pending_post_upload_keys', None)
                return jsonify({'error': '실제 이미지 파일만 게시물에 등록할 수 있습니다.'}), 400
            post = Post(user_id=user_id, caption=payload.get('caption'), media_url=','.join(f'sb:{key}' for key in keys))
            db.session.add(post)
            db.session.commit()
            session.pop('pending_post_upload_keys', None)
            return jsonify({'redirect': url_for('main.index')})

    media_files = request.files.getlist('media_file')
    saved_urls = []

    media_files = [file for file in media_files if file and file.filename]
    if not media_files or len(media_files) > 10:
        flash('게시물에는 이미지 파일을 1개 이상 10개 이하로 선택해주세요.')
        return redirect(url_for('main.index'))

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    for file in media_files:
        extension = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if extension not in allowed_extensions or not (file.mimetype or '').lower().startswith('image/'):
            flash('이미지 파일만 업로드할 수 있습니다.')
            return redirect(url_for('main.index'))
        header = file.stream.read(32)
        file.stream.seek(0)
        if not has_image_signature(header):
            flash('실제 이미지 파일만 업로드할 수 있습니다.')
            return redirect(url_for('main.index'))

    for file in media_files:
        saved_urls.append(upload_media(file, 'story-posts', resource_type='image'))

    media_url = ','.join(saved_urls) if saved_urls else None

    # DB 저장 (현재 로그인 유저 ID로 저장)
    post = Post(
        user_id=user_id,
        caption=caption,
        media_url=media_url
    )
    db.session.add(post)
    db.session.commit()

    return redirect(url_for('main.index'))


# 3. 좋아요 토글
@bp.route('/like/<int:post_id>', methods=['POST'])
def like(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    post = Post.query.get_or_404(post_id)
    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        new_like = PostLike(post_id=post_id, user_id=user_id)
        db.session.add(new_like)
        liked = True
        if post.user_id != user_id:
            actor = User.query.get(user_id)
            notification = Notification(
                recipient_id=post.user_id, actor_id=user_id, post_id=post.id,
                type='post_like', is_read=False, created_at=utc_now_naive(),
            )
            db.session.add(notification)
    notification = notification if liked and post.user_id != user_id else None

    db.session.commit()

    if notification:
        _emit_post_notification(notification, actor, post, '님이 회원님의 게시물을 좋아합니다.')

    like_count = PostLike.query.filter_by(post_id=post_id).count()

    return jsonify({
        'success': True,
        'liked': liked,
        'like_count': like_count
    })


@bp.route('/repost/<int:post_id>', methods=['POST'])
def repost(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    post = Post.query.get_or_404(post_id)
    existing_repost = PostRepost.query.filter_by(post_id=post.id, user_id=user_id).first()
    if existing_repost:
        db.session.delete(existing_repost)
        reposted = False
    else:
        db.session.add(PostRepost(post_id=post.id, user_id=user_id))
        reposted = True

    db.session.commit()
    return jsonify({'success': True, 'reposted': reposted})


# 4. 댓글 작성 기능
@bp.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')

    if content and content.strip():
        new_comment = PostComment(
            post_id=post_id,
            user_id=user_id,
            content=content.strip()
        )
        db.session.add(new_comment)
        db.session.commit()

        comment_count = PostComment.query.filter_by(post_id=post_id).count()

        # 작성자 정보 구하기 (g.user 우선, 없으면 DB 조회)
        user = g.user if (hasattr(g, 'user') and g.user) else User.query.get(user_id)
        user_name = user.username if user else session.get('username', '')
        if post.user_id != user_id:
            notification = Notification(
                recipient_id=post.user_id, actor_id=user_id, post_id=post.id,
                message=new_comment.content,
                type='post_comment', is_read=False, created_at=utc_now_naive(),
            )
            db.session.add(notification)
            db.session.commit()
            _emit_post_notification(
                notification, user, post, '님이 회원님의 게시물에 댓글을 남겼습니다.',
                comment_content=new_comment.content,
            )

        # profile_img_url 경로 생성 (Flask static 파일 경로 처리)
        profile_img_url = url_for('static', filename=user.profile_img_url) if (user and user.profile_img_url) else ''

        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'user_id': new_comment.user_id,
                'user_name': user_name,
                'profile_img_url': profile_img_url,
                'content': new_comment.content,
                'created_at': utc_isoformat(new_comment.created_at)
                if hasattr(new_comment, 'created_at') and new_comment.created_at else ''
            },
            'comment_count': comment_count
        })

    return jsonify({'success': False, 'message': '내용을 입력해주세요.'}), 400


def _emit_post_notification(notification, actor, post, action, comment_content=None):
    from story.events import socketio
    unread_count = Notification.query.filter_by(recipient_id=notification.recipient_id, is_read=False).count()
    socketio.emit('new_notification', {
        'id': notification.id,
        'type': notification.type,
        'post_id': notification.post_id,
        'actor_id': actor.id,
        'actor_username': actor.username,
        'actor_profile_img_url': actor.profile_img_url,
        'message': f'{actor.username}{action}',
        'comment_content': comment_content if notification.type == 'post_comment' else None,
        'url': url_for('main.index'),
        'created_at': notification.created_at.isoformat(),
        'unread_count': unread_count,
    }, to=f'user_{notification.recipient_id}')


# 5. 댓글 수정 기능
@bp.route('/comment/edit/<int:comment_id>', methods=['POST'])
def edit_comment(comment_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    comment_obj = PostComment.query.get_or_404(comment_id)

    # 본인이 작성한 댓글인지 권한 확인
    if comment_obj.user_id != user_id:
        return jsonify({'success': False, 'message': '수정 권한이 없습니다.'}), 403

    new_content = request.form.get('content')
    if not new_content or not new_content.strip():
        return jsonify({'success': False, 'message': '수정할 내용을 입력해주세요.'}), 400

    comment_obj.content = new_content.strip()
    db.session.commit()

    return jsonify({'success': True, 'message': '댓글이 수정되었습니다.'})


@bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    comment_obj = PostComment.query.get_or_404(comment_id)
    if comment_obj.user_id != user_id:
        return jsonify({'success': False, 'message': '삭제 권한이 없습니다.'}), 403

    post_id = comment_obj.post_id
    db.session.delete(comment_obj)
    db.session.commit()

    comment_count = PostComment.query.filter_by(post_id=post_id).count()
    return jsonify({
        'success': True,
        'message': '댓글이 삭제되었습니다.',
        'comment_count': comment_count
    })


# 6. 게시물 삭제 기능 [신규 추가]
@bp.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    post = Post.query.get_or_404(post_id)

    # 본인이 작성한 게시물인지 권한 확인
    if post.user_id != user_id:
        return jsonify({'success': False, 'message': '삭제 권한이 없습니다.'}), 403

    # 관련 데이터도 게시물과 함께 삭제한다. 벌크 삭제로 ORM cascade에 의존하지 않는다.
    PostLike.query.filter_by(post_id=post_id).delete()
    PostComment.query.filter_by(post_id=post_id).delete()
    PostRepost.query.filter_by(post_id=post_id).delete()
    Notification.query.filter_by(post_id=post_id).delete()

    db.session.delete(post)
    db.session.commit()

    return jsonify({'success': True, 'message': '게시물이 삭제되었습니다.'})


# 7. 게시물 수정 기능 [신규 추가]
@bp.route('/edit/<int:post_id>', methods=['POST'])
def edit_post(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    post = Post.query.get_or_404(post_id)

    # 본인이 작성한 게시물인지 권한 확인
    if post.user_id != user_id:
        return jsonify({'success': False, 'message': '수정 권한이 없습니다.'}), 403

    caption = request.form.get('caption', '')
    post.caption = caption
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '게시물이 수정되었습니다.',
        'caption': post.caption
    })
