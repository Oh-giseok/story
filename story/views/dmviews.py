# story/views/dmviews.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, g
from story.models import db, Conversation, Message, MessageRead, User
from datetime import datetime

bp = Blueprint('dm', __name__, url_prefix='/dm')


@bp.before_request
def check_login():
    current_user_id = session.get('user_id')
    if not current_user_id and hasattr(g, 'user') and g.user:
        current_user_id = g.user.id

    if not current_user_id:
        if request.is_json or request.path.startswith('/dm/conversations'):
            return jsonify({'error': '로그인이 필요합니다.'}), 401

        if request.endpoint in ['dm.user_list', 'dm.chat_room', 'dm.chat_main']:
            return redirect(url_for('auth.login'))


# 통합 메인 뷰 (데스크톱: 좌측 목록 + 우측 채팅 / 모바일: 조건별 분기)
@bp.route('/')
@bp.route('/users')
@bp.route('/chat')
def user_list():
    current_user_id = session.get('user_id') or (g.user.id if hasattr(g, 'user') and g.user else None)

    target_id = request.args.get('target_id', default=None, type=int)
    keyword = request.args.get('q', '', type=str)

    # 1. 최근 대화 목록 조회
    conversations = Conversation.query.filter(
        (Conversation.user_id1 == current_user_id) | (Conversation.user_id2 == current_user_id)
    ).all()

    active_chat_users = []
    for conv in conversations:
        tid = conv.user_id2 if conv.user_id1 == current_user_id else conv.user_id1
        tuser = User.query.get(tid)
        if tuser:
            last_msg = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
            active_chat_users.append({
                'user': tuser,
                'last_message': last_msg
            })

    # 최신 메시지 작성일 기준 내림차순 정렬
    active_chat_users.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min,
        reverse=True
    )

    # 2. 대화 가능 대상 유저 목록 (검색 기능 포함)
    query = User.query.filter(User.id != current_user_id)
    if keyword:
        query = query.filter((User.username.contains(keyword)) | (User.name.contains(keyword)))
    all_users = query.all()

    # 3. 선택된 상대방 정보 (target_id가 존재할 때만 조회)
    target_user = User.query.get(target_id) if target_id else None
    target_name = (target_user.name or target_user.username) if target_user else None

    return render_template(
        'dm/chat.html',
        active_chat_users=active_chat_users,
        all_users=all_users,
        keyword=keyword,
        target_id=target_id,
        target_name=target_name,
        target_user=target_user  # <-- target_user 객체 전달 반영 완료
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