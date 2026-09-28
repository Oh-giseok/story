import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, session, g
from werkzeug.utils import secure_filename
from story import db
from story.models import Post, User, PostLike, PostComment

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
    return render_template('post/post_list.html', posts=posts)


# 2. 게시물 등록 처리
@bp.route('/create', methods=['POST'])
def _create():
    user_id = get_current_user_id()
    if not user_id:
        # 로그인하지 않은 유저인 경우 로그인 페이지 등으로 이동 또는 에러 처리
        return redirect(url_for('auth.login'))  # 사용하시는 로그인 라우트명으로 맞추어 사용해주세요.

    caption = request.form.get('caption')
    media_files = request.files.getlist('media_file')
    saved_urls = []

    if media_files:
        today = datetime.now().strftime('%Y%m%d')
        upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
        os.makedirs(upload_folder, exist_ok=True)

        for file in media_files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                saved_urls.append(f'/static/photo/{today}/{filename}')

    media_url = ','.join(saved_urls) if saved_urls else None

    # 4. DB 저장 (현재 로그인 유저 ID로 저장)
    post = Post(
        user_id=user_id,
        caption=caption,
        media_url=media_url
    )
    db.session.add(post)
    db.session.commit()

    return redirect(url_for('post._list'))


# 3. 좋아요 토글
@bp.route('/like/<int:post_id>', methods=['POST'])
def like(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        new_like = PostLike(post_id=post_id, user_id=user_id)
        db.session.add(new_like)
        liked = True

    db.session.commit()

    like_count = PostLike.query.filter_by(post_id=post_id).count()

    return jsonify({
        'success': True,
        'liked': liked,
        'like_count': like_count
    })


# 4. 댓글 작성 기능
@bp.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    content = request.form.get('content')

    if content and content.strip():
        new_comment = PostComment(
            post_id=post_id,
            user_id=user_id,  # 현재 로그인 유저 ID
            content=content.strip()
        )
        db.session.add(new_comment)
        db.session.commit()

        comment_count = PostComment.query.filter_by(post_id=post_id).count()

        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'user_id': new_comment.user_id,
                'content': new_comment.content,
                'created_at': new_comment.created_at.strftime('%Y-%m-%d %H:%M')
            },
            'comment_count': comment_count
        })

    return jsonify({'success': False, 'message': '내용을 입력해주세요.'}), 400