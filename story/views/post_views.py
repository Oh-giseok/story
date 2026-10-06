import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, session, g, flash
from werkzeug.utils import secure_filename
from story import db
from story.models import Post, User, PostLike, PostComment, PostRepost, Story, Notification
from story.time_utils import utc_isoformat, kst_now_naive, utc_now_naive

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
    story_list = Story.query.filter(Story.expires_at > kst_now_naive()).order_by(Story.create_date.desc()).all()
    user_id = get_current_user_id()
    reposted_post_ids = {
        repost.post_id
        for repost in PostRepost.query.filter_by(user_id=user_id).all()
    } if user_id else set()
    return render_template(
        'post/post_list.html', posts=posts, story_list=story_list,
        reposted_post_ids=reposted_post_ids
    )


# 2. 게시물 등록 처리
@bp.route('/create', methods=['GET', 'POST'])
def _create():
    user_id = get_current_user_id()
    if not user_id:
        # 로그인하지 않은 유저인 경우 로그인 페이지 등으로 이동 또는 에러 처리
        return redirect(url_for('auth.login'))  # 사용하시는 로그인 라우트명으로 맞추어 사용해주세요.

    if request.method == 'GET':
        return render_template('post/post_form.html')

    caption = request.form.get('caption')
    media_files = request.files.getlist('media_file')
    saved_urls = []

    media_files = [file for file in media_files if file and file.filename]
    if not media_files:
        flash('사진이나 동영상을 선택해주세요.')
        return redirect(url_for('main.index'))

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'webm'}
    for file in media_files:
        extension = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if extension not in allowed_extensions:
            flash('지원하지 않는 사진 또는 동영상 형식입니다.')
            return redirect(url_for('main.index'))

    today = kst_now_naive().strftime('%Y%m%d')
    upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
    os.makedirs(upload_folder, exist_ok=True)

    for file in media_files:
        safe_name = secure_filename(file.filename).replace(',', '_')
        filename = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        saved_urls.append(f'/static/photo/{today}/{filename}')

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
    user_id = get_current_user_id()
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
            actor = g.user if (hasattr(g, 'user') and g.user) else User.query.get(user_id)
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

    # 해당 게시물의 댓글 및 좋아요도 함께 연쇄 삭제 (ORMB/relationship 캐스케이드가 설정되지 않은 경우를 대비)
    PostLike.query.filter_by(post_id=post_id).delete()
    PostComment.query.filter_by(post_id=post_id).delete()

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
