from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db=SQLAlchemy()

class User(db.Model):
    __tablename__='user'
    id=db.Column(db.Integer,primary_key=True,autoincrement=True)
    username=db.Column(db.String(50),unique=True,nullable=False)
    email=db.Column(db.String(100),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    name=db.Column(db.String(50))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class Conversation(db.Model):
    __tablename__='conversation'
    id=db.Column(db.Integer,primary_key=True,autoincrement=True)
    user_id1=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    user_id2=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('user_id1','user_id2',name='unique_user_pair'),)
    messages=db.relationship('Message',backref='conversation',lazy=True,cascade="all, delete-orphan")

class Message(db.Model):
    __tablename__='message'
    id=db.Column(db.Integer,primary_key=True,autoincrement=True)
    conversation_id=db.Column(db.Integer,db.ForeignKey('conversation.id'),nullable=False)
    sender_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    text=db.Column(db.Text,nullable=True)
    img_url=db.Column(db.String(255),nullable=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    reads=db.relationship('MessageRead',backref='message',lazy=True,cascade="all, delete-orphan")
    def to_dict(self):
        read_user_ids={r.user_id for r in self.reads}
        read_user_ids.add(self.sender_id)
        unread_count=max(0,2-len(read_user_ids))
        return {'id':self.id,'conversation_id':self.conversation_id,'sender_id':self.sender_id,'text':self.text,'img_url':self.img_url,'created_at':self.created_at.strftime('%Y-%m-%d %H:%M:%S'),'unread_count':unread_count}

class MessageRead(db.Model):
    __tablename__='message_read'
    id=db.Column(db.Integer,primary_key=True,autoincrement=True)
    message_id=db.Column(db.Integer,db.ForeignKey('message.id'),nullable=False)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    read_at=db.Column(db.DateTime,default=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('message_id','user_id',name='unique_message_read'),)