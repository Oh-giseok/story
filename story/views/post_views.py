from flask import Blueprint, render_template, request, redirect, url_for
from story import db
from story.models import Post, User

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
    file = request.files.get('media_file')

    media_url = None
    if media_file and media_file.filename != '':
        # 1. 저장 경로 지정 : static/photo/오늘날짜(YYYY,MM,DD) 폴더 생성
        today = datetime.now().strftime('%Y-%m-%d')
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], today)
        os.makedirs(upload_folder, exist_ok=True)

        # 2. 보안 적용 파일명 및 파일 실제 저장
        filename = secure_filename(media_file.filename)
        file_path = os.path.join(upload_folder, filename)
        media_file.save(file_path)

        # 3. DB 및 웹에서 보여줄 static 기준 상대 경로 생성
        media_url = f'/static/photo/{today}/{filename}'

    # 4. Post DB 객체 생성 및 저장
    post = Post(
        user_id=1,
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