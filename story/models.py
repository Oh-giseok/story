#models.py
from story import db
from datetime import datetime

from datetime import datetime
from story import db  # __init__.py의 db 객체 임포트



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

class Conversation(db.Model):
    __tablename__ = 'conversation'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id1 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id2 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id1', 'user_id2', name='unique_user_pair'),)
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")


class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=True)
    img_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reads = db.relationship('MessageRead', backref='message', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        read_user_ids = {r.user_id for r in self.reads}
        read_user_ids.add(self.sender_id)
        unread_count = max(0, 2 - len(read_user_ids))
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_id': self.sender_id,
            'text': self.text,
            'img_url': self.img_url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'unread_count': unread_count
        }


class MessageRead(db.Model):
    __tablename__ = 'message_read'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='unique_message_read'),)

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