#models.py
from story import db


#회원정보 DB
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False) #ID
    password_hash = db.Column(db.String(150), nullable=False) #PW
    email = db.Column(db.String(200), unique=True, nullable=False) #Email
    name = db.Column(db.String(200),nullable=False) #이름
    intro = db.Column(db.Text) #자기소개
    profile_img_url =db.Column(db.String(200)) #프로필 이미지
    birth = db.Column(db.DateTime, nullable=False) #생년월일
    created_at = db.Column(db.DateTime, nullable=False) #계정 생성일
    updated_at = db.Column(db.DateTime, nullable=False) #계정 정보 수정일