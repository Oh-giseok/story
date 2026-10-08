from flask import session, request
from flask_socketio import SocketIO, emit, join_room
from flask_login import current_user
from story.models import Conversation, Friendship, Message, MessageRead, User, db

socketio = SocketIO()
PRESENCE_TTL_SECONDS = 60


def _presence_key(user_id):
    return f'user_online:{user_id}'


def _session_key(user_id):
    return f'user_socket_sessions:{user_id}'


def _set_online(user_id, sid):
    from story import redis_client
    if redis_client:
        redis_client.sadd(_session_key(user_id), sid)
        redis_client.expire(_session_key(user_id), PRESENCE_TTL_SECONDS)
        redis_client.setex(_presence_key(user_id), PRESENCE_TTL_SECONDS, '1')


def _touch_online(user_id, sid):
    from story import redis_client
    if redis_client:
        key = _session_key(user_id)
        redis_client.sadd(key, sid)
        redis_client.expire(key, PRESENCE_TTL_SECONDS)
        redis_client.setex(_presence_key(user_id), PRESENCE_TTL_SECONDS, '1')


def _set_offline_if_last_session(user_id, sid):
    from story import redis_client
    if not redis_client:
        return False
    key = _session_key(user_id)
    redis_client.srem(key, sid)
    if redis_client.scard(key):
        return False
    redis_client.delete(key, _presence_key(user_id))
    return True


def _dm_peer_ids(user_id):
    conversations = Conversation.query.filter(
        (Conversation.user_id1 == user_id) | (Conversation.user_id2 == user_id)
    ).all()
    peer_ids = {
        conversation.user_id2 if conversation.user_id1 == user_id else conversation.user_id1
        for conversation in conversations
    }
    friendships = Friendship.query.filter(
        ((Friendship.user_low_id == user_id) | (Friendship.user_high_id == user_id)),
        Friendship.status == 'accepted'
    ).all()
    peer_ids.update(
        friendship.user_high_id if friendship.user_low_id == user_id else friendship.user_low_id
        for friendship in friendships
    )
    return peer_ids


def _publish_presence(user_id, status):
    payload = {'user_id': user_id, 'status': status}
    for peer_id in _dm_peer_ids(user_id):
        socketio.emit('presence_change', payload, to=f'user_{peer_id}')


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
    try:
        _set_online(user_id, request.sid)
        _publish_presence(user_id, 'online')
        peers = User.query.filter(User.id.in_(_dm_peer_ids(user_id))).all()
        statuses = {str(peer.id): peer.connection_status for peer in peers}
        emit('presence_snapshot', statuses, to=request.sid)
    except Exception:
        db.session.rollback()


@socketio.on('heartbeat')
def handle_heartbeat(data=None):
    user_id = authenticated_user_id()
    if not user_id:
        return
    try:
        _touch_online(user_id, request.sid)
    except Exception:
        # An expired Redis session key is recreated by the heartbeat.
        pass


@socketio.on('disconnect')
def handle_disconnect(reason=None):
    user_id = authenticated_user_id()
    if not user_id:
        return
    try:
        if _set_offline_if_last_session(user_id, request.sid):
            _publish_presence(user_id, 'offline')
    except Exception:
        db.session.rollback()


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
