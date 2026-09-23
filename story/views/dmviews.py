from flask import Blueprint,render_template,request,jsonify
from story.models import db,Conversation,Message,MessageRead,User

bp=Blueprint('dm',__name__,url_prefix='/dm')

@bp.route('/')
def chat_room():
    target_id=request.args.get('target_id',type=int) or 2
    target_user=User.query.get(target_id)
    target_name=target_user.name if target_user and target_user.name else (target_user.username if target_user else f"사용자 {target_id}")
    return render_template('dm/chat.html',target_id=target_id,target_name=target_name)

@bp.route('/conversations',methods=['POST'])
def get_or_create_conversation():
    data=request.get_json()
    u1,u2=sorted([data.get('user_id1'),data.get('user_id2')])
    conv=Conversation.query.filter_by(user_id1=u1,user_id2=u2).first()
    if not conv:
        conv=Conversation(user_id1=u1,user_id2=u2)
        db.session.add(conv)
        db.session.commit()
    return jsonify({'conversation_id':conv.id})

@bp.route('/conversations/<int:conv_id>/messages',methods=['GET'])
def get_messages(conv_id):
    user_id=request.args.get('user_id',type=int)
    messages=Message.query.filter_by(conversation_id=conv_id).order_by(Message.created_at.asc()).all()
    if user_id:
        for m in messages:
            if not MessageRead.query.filter_by(message_id=m.id,user_id=user_id).first():
                db.session.add(MessageRead(message_id=m.id,user_id=user_id))
        db.session.commit()
    return jsonify([msg.to_dict() for msg in messages])