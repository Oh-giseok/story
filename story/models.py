from story import db


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)  # ID
    password_hash = db.Column(db.String(150), nullable=False)  # PW
    email = db.Column(db.String(200), unique=True, nullable=False)  # Email
    name = db.Column(db.String(200), nullable=False)  # 이름
    intro = db.Column(db.Text)  # 자기소개
    profile_img_url = db.Column(db.String(200))  # 프로필 이미지
    birth = db.Column(db.DateTime, nullable=False)  # 생년월일

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# 2. 인스타 스토리 DB
class Story(db.Model):
    __tablename__ = 'story'

    id = db.Column(db.Integer, primary_key=True)

    # 어떤 회원이 이 스토리를 올렸는지 User 테이블과 엮어주는 외래키
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('story_set', cascade='all, delete-orphan'))

    content_url = db.Column(db.String(200), nullable=False)  # 업로드된 스토리 미디어 파일 경로
    caption = db.Column(db.Text)  # 스토리 본문 글귀
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # 스토리 작성 시간