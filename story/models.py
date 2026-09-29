from datetime import datetime
from story import db  # __init__.py의 db 객체 임포트
from flask_login import UserMixin

class User(db.Model, UserMixin):

    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(200))
    intro = db.Column(db.Text)
    profile_img_url = db.Column(db.String(200))
    birth = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(db.Model):
    __tablename__ = 'conversation'
    __table_args__ = (
        db.UniqueConstraint('user_id1', 'user_id2', name='unique_user_pair'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id1 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id2 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")


class Message(db.Model):
    __tablename__ = 'message'
    __table_args__ = {'extend_existing': True}

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
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='unique_message_read'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)


class Post(db.Model):
    __tablename__ = 'post'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    caption = db.Column(db.Text)
    media_url = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref=db.backref('post_set', cascade='all, delete-orphan'))


class PostLike(db.Model):
    __tablename__ = 'post_likes'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_user_like'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    # [추가] Post 모델과의 관계
    post = db.relationship('Post', backref=db.backref('likes', cascade='all, delete-orphan'))
    # [추가] User 모델과의 관계
    user = db.relationship('User', backref=db.backref('post_like_set', cascade='all, delete-orphan'))

class PostComment(db.Model):
    __tablename__ = 'post_comments'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # [수정/추가] Post 모델과 연결 -> post.comments 로 댓글 목록 접근
    post = db.relationship('Post', backref=db.backref('comments', cascade='all, delete-orphan'))
    # User 모델과 연결 -> comment.user.username 으로 작성자 아이디 접근
    user = db.relationship('User', backref=db.backref('comment_set', cascade='all, delete-orphan'))

class Reels(db.Model):
    __tablename__ = 'reels'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_url = db.Column(db.Text, nullable=False)
    thumbnail_url = db.Column(db.String(250), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Reels_Likes(db.Model):
    __tablename__ = 'reel_likes'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'reel_id', name='unique_user_reel_like'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'reel_id', name='unique_user_reel_like'),)


class Comments(db.Model):
    __tablename__ = 'comments'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Story(db.Model):
    __tablename__ = 'story'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('story_set'))
    media_url = db.Column(db.String(200), nullable=False)
    thumbnail_url = db.Column(db.String(200))
    caption = db.Column(db.Text)
    create_date = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)


class StoryLikes(db.Model):
    __tablename__ = 'story_likes'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'), nullable=False)
    story = db.relationship('Story', backref=db.backref('like_set'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('story_like_set'))