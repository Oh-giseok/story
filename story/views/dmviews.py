from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, g
from story.models import db, Conversation, Message, MessageRead, User, Friendship
from flask_login import current_user
from datetime import datetime

bp = Blueprint('dm', __name__, url_prefix='/dm')


@bp.before_request
def check_login():
    current_user_id = session.get('user_id') or (
        current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None)
    if not current_user_id and hasattr(g, 'user') and g.user:
        current_user_id = g.user.id
    if not current_user_id:
        if request.is_json or request.path.startswith('/dm/conversations'):
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        if request.endpoint in ['dm.user_list', 'dm.chat_room', 'dm.chat_main']:
            return redirect(url_for('auth.login'))


def get_active_chat_users(user_id, current_target_id=None):
    if not user_id:
        return []

    user_id = int(user_id)

    conversations = Conversation.query.filter(
        (Conversation.user_id1 == user_id) | (Conversation.user_id2 == user_id)
    ).all()
    active_chat_users = []
    for conv in conversations:
        tid = conv.user_id2 if conv.user_id1 == user_id else conv.user_id1
        tuser = User.query.get(tid)
        if tuser:
            last_msg = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
            if last_msg:
                partner_msg_ids = [m.id for m in Message.query.filter(
                    Message.conversation_id == conv.id,
                    Message.sender_id != user_id
                ).all()]

                unread_count = 0
                if partner_msg_ids:
                    read_msg_ids = {r.message_id for r in MessageRead.query.filter(
                        MessageRead.message_id.in_(partner_msg_ids),
                        MessageRead.user_id == user_id
                    ).all()}
                    unread_count = len(partner_msg_ids) - len(read_msg_ids)

                is_partner_last = (int(last_msg.sender_id) != user_id)

                if not is_partner_last:
                    has_unread = False
                    unread_count = 0
                else:
                    has_unread = (unread_count > 0)

                if current_target_id and int(current_target_id) == tid:
                    has_unread = False
                    unread_count = 0

                active_chat_users.append({
                    'user': tuser,
                    'last_message': last_msg,
                    'unread_count': unread_count,
                    'has_unread': has_unread
                })
    active_chat_users.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min,
        reverse=True
    )
    return active_chat_users


@bp.route('/')
@bp.route('/users')
@bp.route('/chat')
def user_list():
    current_user_id = session.get('user_id') or (
        current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None) or (
                          g.user.id if hasattr(g, 'user') and g.user else None)
    target_id = request.args.get('target_id', default=None, type=int)
    keyword = request.args.get('q', '', type=str)

    active_chat_users = get_active_chat_users(current_user_id, target_id)

    friends = []
    if current_user_id:
        accepted_friendships = Friendship.query.filter(
            ((Friendship.user_low_id == current_user_id) | (Friendship.user_high_id == current_user_id)),
            Friendship.status == 'accepted'
        ).all()

        friend_ids = set()
        for f in accepted_friendships:
            fid = f.user_high_id if f.user_low_id == current_user_id else f.user_low_id
            if fid != int(current_user_id):
                friend_ids.add(fid)

        if friend_ids:
            friend_query = User.query.filter(User.id.in_(friend_ids))
            if keyword:
                friend_query = friend_query.filter((User.username.contains(keyword)) | (User.name.contains(keyword)))
            friends = friend_query.all()

    target_user = User.query.get(target_id) if target_id else None
    target_name = (target_user.name or target_user.username) if target_user else None

    return render_template(
        'dm/chat.html',
        active_chat_users=active_chat_users,
        friends=friends,
        keyword=keyword,
        target_id=target_id,
        target_name=target_name,
        target_user=target_user
    )


@bp.route('/conversations', methods=['POST'])
def get_or_create_conversation():
    data = request.get_json() or {}
    u1, u2 = sorted([int(data.get('user_id1')), int(data.get('user_id2'))])
    if not u1 or not u2:
        return jsonify({'error': '유효하지 않은 유저 ID입니다.'}), 400
    conv = Conversation.query.filter_by(user_id1=u1, user_id2=u2).first()
    if not conv:
        conv = Conversation(user_id1=u1, user_id2=u2)
        db.session.add(conv)
        db.session.commit()
    return jsonify({'conversation_id': conv.id})


@bp.route('/conversations/<int:conv_id>/messages', methods=['GET'])
def get_messages(conv_id):
    user_id = request.args.get('user_id', type=int)
    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.created_at.asc()).all()
    if user_id and messages:
        updated = False
        for m in messages:
            already_read = MessageRead.query.filter_by(message_id=m.id, user_id=user_id).first()
            if not already_read:
                db.session.add(MessageRead(message_id=m.id, user_id=user_id))
                updated = True
        if updated:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    return jsonify([msg.to_dict() for msg in messages])


@bp.route('/leave', methods=['POST'])
def leave_conversation():
    data = request.get_json() or {}
    current_user_id = session.get('user_id') or (
        current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None) or (
                          g.user.id if hasattr(g, 'user') and g.user else None)
    target_id = data.get('target_id')
    if not current_user_id or not target_id:
        return jsonify({'error': '잘못된 요청입니다.'}), 400
    u1, u2 = sorted([int(current_user_id), int(target_id)])
    conv = Conversation.query.filter_by(user_id1=u1, user_id2=u2).first()
    if conv:
        try:
            msg_ids = [m.id for m in Message.query.filter_by(conversation_id=conv.id).all()]
            if msg_ids:
                MessageRead.query.filter(MessageRead.message_id.in_(msg_ids)).delete(synchronize_session=False)
            Message.query.filter_by(conversation_id=conv.id).delete(synchronize_session=False)
            db.session.delete(conv)
            db.session.commit()
            return jsonify({'success': True, 'message': '대화 데이터가 완전히 삭제되었습니다.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'대화방 삭제 실패: {str(e)}'}), 500
    return jsonify({'error': '대화방을 찾을 수 없습니다.'}), 404