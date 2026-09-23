from flask_socketio import SocketIO,join_room,emit
from story.models import db,Message,MessageRead

socketio=SocketIO()

@socketio.on('join_room')
def handle_join_room(data):
    join_room(str(data['conversation_id']))

@socketio.on('send_message')
def handle_send_message(data):
    conv_id=data.get('conversation_id')
    sender_id=data.get('sender_id')
    new_msg=Message(conversation_id=conv_id,sender_id=sender_id,text=data.get('text'),img_url=data.get('img_url'))
    db.session.add(new_msg)
    db.session.flush()
    db.session.add(MessageRead(message_id=new_msg.id,user_id=sender_id))
    db.session.commit()
    emit('receive_message',new_msg.to_dict(),to=str(conv_id))

@socketio.on('mark_read')
def handle_mark_read(data):
    conv_id=data.get('conversation_id')
    user_id=data.get('user_id')
    msgs=Message.query.filter_by(conversation_id=conv_id).all()
    updated=False
    for m in msgs:
        if not MessageRead.query.filter_by(message_id=m.id,user_id=user_id).first():
            db.session.add(MessageRead(message_id=m.id,user_id=user_id))
            updated=True
    if updated:
        db.session.commit()
        emit('update_read_status',{'conversation_id':conv_id},to=str(conv_id))