import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from story import db
from story.models import Post, User, PostLike  # PostLike 추가

# /post 경로로 들어오는 요청들을 처리할 블루프린트 생성
bp = Blueprint('post', __name__, url_prefix='/post')

# 1. 게시물 목록 보기
@bp.route('/list')
def _list():
    # 최신순(created_at 내림차순)으로 모든 게시물 DB 조회
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('post/post_list.html', posts=posts)

# 2. 게시물 등록 처리
@bp.route('/create', methods=['POST'])
def _create():
    caption = request.form.get('caption')

    # [수정 Point 1] getlist()는 파일 객체들의 '리스트(List)'를 반환하므로
    # 변수명을 직관적으로 media_files(복수형)로 변경했습니다.
    media_files = request.files.getlist('media_file')

    # 저장된 각 파일들의 상대 경로(/static/photo/YYYYMMDD/파일명)를 담을 리스트 생성
    saved_urls = []

    # [수정 Point 2] media_files는 리스트 형태이므로, 기존 코드처럼 media_files.filename으로 직접 접근하면 에러가 납니다.
    # 리스트에 선택된 파일이 있는지 확인 후, 반복문(for)으로 하나씩 꺼내어 처리합니다.
    if media_files:
        # 1. 오늘 날짜 폴더 생성 (static/photo/YYYYMMDD)
        today = datetime.now().strftime('%Y%m%d')
        upload_folder = os.path.join(current_app.root_path, 'static/photo', today)
        os.makedirs(upload_folder, exist_ok=True)

        # [수정 Point 3] 반복문을 통해 업로드된 여러 개 파일들을 하나씩 저장합니다.
        for file in media_files:
            # 빈 파일이 넘어오는 경우(선택 안 함)를 방지하기 위해 파일명 체크
            if file and file.filename != '':
                # 2. 파일 저장
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                # 3. 개별 파일의 DB 및 웹 접근 경로를 리스트에 추가
                saved_urls.append(f'/static/photo/{today}/{filename}')

    # [수정 Point 4] 여러 경로들을 쉼표(,)로 구분된 하나의 문자열로 결합합니다.
    # 예시: '/static/photo/20260330/img1.jpg,/static/photo/20260330/img2.jpg'
    # 저장할 파일이 하나도 없으면 None으로 설정됩니다.
    media_url = ','.join(saved_urls) if saved_urls else None

    # 4. DB 저장
    post = Post(
        user_id=1,  # 임시 사용자 ID
        caption=caption,
        media_url=media_url
    )
    db.session.add(post)
    db.session.commit()

    return redirect(url_for('post._list'))

# 3. 좋아요 토글 (등록 / 취소)
@bp.route('/like/<int:post_id>', methods=['POST'])
def like(post_id):
    # 로그인 구현 전 임시 1번 처리
    user_id = 1

    # 이미 해당 유저가 이 글에 좋아요를 눌렀는지 확인
    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        # 이미 눌렀다면 -> 좋아요 취소(삭제)
        db.session.delete(existing_like)
    else:
        # 안 눌렀다면 -> 좋아요 등록(추가)
        new_like = PostLike(post_id=post_id, user_id=user_id)
        db.session.add(new_like)

    db.session.commit()
    return redirect(url_for('post._list'))