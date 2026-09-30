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
    if hasattr(g, 'user') and g.user:
        return g.user.id
    if 'user_id' in session:
        return session['user_id']
    return None


# 1. 게시물 목록 보기
@bp.route('/')
def _list():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('post/post_list.html', posts=posts)


# 2. 게시물 등록 (GET: 업로드 폼 / POST: 업로드 처리)
@bp.route('/create', methods=['GET', 'POST'])
def _create():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
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

        post = Post(
            user_id=user_id,
            caption=caption,
            media_url=media_url
        )
        db.session.add(post)
        db.session.commit()
    # DB 저장 (현재 로그인 유저 ID로 저장)
    post = Post(
        user_id=user_id,
        caption=caption,
        media_url=media_url
    )
    db.session.add(post)
    db.session.commit()

        return redirect(url_for('post._list'))

    # GET 요청 시 포스트 업로드 작성 페이지 렌더링
    return render_template('post/post_form.html')


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
            user_id=user_id,
            content=content.strip()
        )
        db.session.add(new_comment)
        db.session.commit()

        comment_count = PostComment.query.filter_by(post_id=post_id).count()

        # 작성자 정보 구하기 (g.user 우선, 없으면 DB 조회)
        user = g.user if (hasattr(g, 'user') and g.user) else User.query.get(user_id)
        user_name = user.username if user else session.get('username', '')

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
                'created_at': new_comment.created_at.strftime('%Y-%m-%d %H:%M')
                if hasattr(new_comment, 'created_at') and new_comment.created_at else ''
            },
            'comment_count': comment_count
        })

    return jsonify({'success': False, 'message': '내용을 입력해주세요.'}), 400


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