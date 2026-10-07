from flask import session
from flask_socketio import SocketIO, emit, join_room
from flask_login import current_user
from story.models import Conversation, Message, MessageRead, db

socketio = SocketIO()


def authenticated_user_id():
    user_id = current_user.id if current_user.is_authenticated else session.get('user_id')
    try:
        return int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        return None


@socketio.on('connect')
def handle_connect(auth=None):
    user_id = authenticated_user_id()
    if not user_id:
        return False
    join_room(f'user_{user_id}')


@socketio.on('join_room')
def handle_join_room(data):
    user_id = authenticated_user_id()
    conv_id = data.get('conversation_id') if isinstance(data, dict) else None
    conversation = Conversation.query.get(conv_id) if conv_id else None
    if conversation and user_id in (conversation.user_id1, conversation.user_id2):
        join_room(str(conversation.id))


@socketio.on('send_message')
def handle_send_message(data):
    user_id = authenticated_user_id()
    conv_id = data.get('conversation_id') if isinstance(data, dict) else None
    text = (data.get('text') or '').strip() if isinstance(data, dict) else ''
    img_url = data.get('img_url') if isinstance(data, dict) else None

    if not user_id or not conv_id or not text:
        return {'success': False, 'message': '메시지를 보낼 수 없습니다. 로그인과 대화 상대를 확인해 주세요.'}

    try:
        conversation = Conversation.query.get(conv_id)
        if not conversation or user_id not in (conversation.user_id1, conversation.user_id2):
            return {'success': False, 'message': '이 대화방에 메시지를 보낼 권한이 없습니다.'}

        new_msg = Message(
            conversation_id=conversation.id,
            sender_id=user_id,
            text=text,
            img_url=img_url
        )
        db.session.add(new_msg)
        db.session.flush()

        already_read = MessageRead.query.filter_by(message_id=new_msg.id, user_id=user_id).first()
        if not already_read:
            db.session.add(MessageRead(message_id=new_msg.id, user_id=user_id))
        db.session.commit()

        emit('receive_message', new_msg.to_dict(), to=str(conversation.id))
        return {'success': True, 'message_id': new_msg.id}
    except Exception as e:
        db.session.rollback()
        print(f"[send_message error] {e}")
        return {'success': False, 'message': '메시지 전송 중 오류가 발생했습니다.'}


@socketio.on('mark_read')
def handle_mark_read(data):
    user_id = authenticated_user_id()
    conv_id = data.get('conversation_id') if isinstance(data, dict) else None

    if not conv_id or not user_id:
        return

    conversation = Conversation.query.get(conv_id)
    if not conversation or user_id not in (conversation.user_id1, conversation.user_id2):
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
        try:
            db.session.commit()
            emit('update_read_status', {'conversation_id': conv_id}, to=str(conv_id))
        except Exception as e:
            db.session.rollback()
            print(f"[mark_read error] {e}")
