from flask_socketio import SocketIO, emit, join_room
from story.models import Message, MessageRead, db

socketio = SocketIO()


@socketio.on('join_room')
def handle_join_room(data):
    conv_id = data.get('conversation_id')
    if conv_id:
        join_room(str(conv_id))


@socketio.on('send_message')
def handle_send_message(data):
    conv_id = data.get('conversation_id')
    sender_id = data.get('sender_id')
    text = data.get('text')
    img_url = data.get('img_url')

    if not conv_id or not sender_id or not text:
        return

    # 1. 새 메시지 저장
    new_msg = Message(
        conversation_id=conv_id,
        sender_id=sender_id,
        text=text,
        img_url=img_url
    )
    db.session.add(new_msg)
    db.session.commit()  # ID 생성을 위해 commit 먼저 수행

    # 2. 보낸 사람의 읽음 처리 등록
    read_record = MessageRead(message_id=new_msg.id, user_id=sender_id)
    db.session.add(read_record)
    db.session.commit()

    # 3. 방에 있는 모든 클라이언트에게 메시지 전송
    emit('receive_message', new_msg.to_dict(), to=str(conv_id))


@socketio.on('mark_read')
def handle_mark_read(data):
    conv_id = data.get('conversation_id')
    user_id = data.get('user_id')

    if not conv_id or not user_id:
        return

    msgs = Message.query.filter_by(conversation_id=conv_id).all()
    updated = False

    for m in msgs:
        # 내가 안 읽은 상대방 메시지만 읽음 처리
        if m.sender_id != user_id:
            already_read = MessageRead.query.filter_by(message_id=m.id, user_id=user_id).first()
            if not already_read:
                db.session.add(MessageRead(message_id=m.id, user_id=user_id))
                updated = True

    if updated:
        db.session.commit()
        emit('update_read_status', {'conversation_id': conv_id}, to=str(conv_id))