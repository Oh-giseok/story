import datetime
from story import db


# 1. 회원정보 테이블
class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)  # ID
    password = db.Column(db.String(200), nullable=False)  # PW
    email = db.Column(db.String(200), unique=True, nullable=False)  # Email
    name = db.Column(db.String(200), nullable=False)  # 이름
    intro = db.Column(db.Text)  # 자기소개
    profile_img_url = db.Column(db.String(200))  # 프로필 이미지
    birth = db.Column(db.DateTime, nullable=False)  # 생년월일
    create_date = db.Column(db.DateTime, nullable=False)
    update_date = db.Column(db.DateTime, nullable=False)


# 2. 인스타 스토리 테이블
class Story(db.Model):
    __tablename__ = 'story'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('story_set'))
    media_url = db.Column(db.String(200), nullable=False)  # 사진/동영상 경로
    thumbnail_url = db.Column(db.String(200), nullable=True)  # 썸네일 이미지 경로
    caption = db.Column(db.Text)  # 스토리 본문 글귀
    create_date = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # 24시간 만료 시간 칸


# 3. 스토리 좋아요 테이블
class StoryLikes(db.Model):
    __tablename__ = 'story_likes'

    id = db.Column(db.Integer, primary_key=True)

    # 어떤 스토리글에 하트가 달렸는지 연결
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'), nullable=False)
    story = db.relationship('Story', backref=db.backref('like_set'))

    # 누가 하트를 눌렀는지 연결
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('story_like_set'))