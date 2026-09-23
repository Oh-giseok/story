#models.py
from datetime import datetime
from story import db


#회원정보 DB
class User(db.Model):
    __tablename__ = 'User'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False) #ID
    password_hash = db.Column(db.String(150), nullable=False) #PW
    email = db.Column(db.String(200), unique=True, nullable=False) #Email
    name = db.Column(db.String(200),nullable=False) #이름
    intro = db.Column(db.Text) #자기소개
    profile_img_url =db.Column(db.String(200)) #프로필 이미지
    birth = db.Column(db.String(200), nullable=False) #생년월일
    created_at = db.Column(db.DateTime,default=datetime.now,nullable=False) #계정 생성일
    updated_at = db.Column(db.DateTime, default=datetime.now,nullable=False) #계정 정보 수정일

class Reels(db.Model):
    __tablename__ = 'reels'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    video_url = db.Column(db.Text, nullable=False)
    thumbnail_url = db.Column(db.String(250), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Reels_Likes(db.Model):
    __tablename__ = 'reel_likes'
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'reel_id', name='unique_user_reel_like'),)

class Comments(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)