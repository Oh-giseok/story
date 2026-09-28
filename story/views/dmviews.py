# story/views/dmviews.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, g
from story.models import db, Conversation, Message, MessageRead, User

bp = Blueprint('dm', __name__, url_prefix='/dm')


@bp.before_request
def check_login():
    # g.user 객체가 존재하는 경우 g.user.id를 가져오도록 수정
    current_user_id = session.get('user_id')
    if not current_user_id and hasattr(g, 'user') and g.user:
        current_user_id = g.user.id

    if not current_user_id:
        # AJAX(JSON) 요청이거나 conversations 경로인 경우 401 JSON 반환 (HTML 리다이렉트 방지)
        if request.is_json or request.path.startswith('/dm/conversations'):
            return jsonify({'error': '로그인이 필요합니다.'}), 401

        # 일반 페이지 접근 시 로그인 페이지로 리다이렉트
        if request.endpoint in ['dm.user_list', 'dm.chat_room']:
            return redirect(url_for('auth.login'))


# 메시지 대상 선택 화면 (상단: 이전 채팅 목록 / 하단: 모든 유저 목록 및 검색)
@bp.route('/users')
def user_list():
    current_user_id = session.get('user_id') or (g.user.id if hasattr(g, 'user') and g.user else None)
    keyword = request.args.get('q', '', type=str)

    # 1. 이전 대화 목록 조회
    conversations = Conversation.query.filter(
        (Conversation.user_id1 == current_user_id) | (Conversation.user_id2 == current_user_id)
    ).all()

    active_chat_users = []
    active_user_ids = set()

    for conv in conversations:
        target_id = conv.user_id2 if conv.user_id1 == current_user_id else conv.user_id1
        target_user = User.query.get(target_id)

        if target_user:
            last_message = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
            active_chat_users.append({
                'user': target_user,
                'last_message': last_message
            })
            active_user_ids.add(target_id)

    # 2. 전체 유저 목록 (검색 기능 포함)
    query = User.query.filter(User.id != current_user_id)
    if keyword:
        query = query.filter((User.username.contains(keyword)) | (User.name.contains(keyword)))

    all_users = query.all()

    return render_template(
        'dm/user_list.html',
        active_chat_users=active_chat_users,
        all_users=all_users,
        keyword=keyword
    )


# 대화 상대와 대화방 API
@bp.route('/conversations', methods=['POST'])
def get_or_create_conversation():
    data = request.get_json() or {}
    u1, u2 = sorted([data.get('user_id1'), data.get('user_id2')])

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

    if user_id:
        for m in messages:
            if not MessageRead.query.filter_by(message_id=m.id, user_id=user_id).first():
                db.session.add(MessageRead(message_id=m.id, user_id=user_id))
        db.session.commit()

    return jsonify([msg.to_dict() for msg in messages])


# 선택된 target_id로 채팅방 진입
@bp.route('/chat')
def chat_room():
    target_id = request.args.get('target_id', type=int)

    if not target_id:
        return redirect(url_for('dm.user_list'))

    target_user = User.query.get_or_404(target_id)
    target_name = target_user.name if target_user.name else target_user.username

    return render_template('dm/chat.html', target_id=target_id, target_name=target_name)