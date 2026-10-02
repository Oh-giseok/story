from flask import Blueprint, request, redirect, url_for, flash, render_template, session, g, current_app, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from urllib.parse import urlparse
import os
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user
from sqlalchemy import or_
from story import db
from story.time_utils import utc_now_naive
from story.forms import UserCreateForm, UserLoginForm, ProfileEditForm
from story.models import User, Post, PostRepost, Reels, Story
from story.models import (
    Conversation, Message, MessageRead,
    PostLike, PostComment, Reels_Likes, Comments, StoryLikes,
    Friendship,
    Notification,
)

bp = Blueprint('auth', __name__, url_prefix='/auth')


def permanently_delete_user(user):
    """Remove a user's content and references before removing the account row."""
    user_id = user.id
    Friendship.query.filter(or_(
        Friendship.user_low_id == user_id,
        Friendship.user_high_id == user_id,
        Friendship.requested_by_id == user_id,
    )).delete(synchronize_session=False)
    Notification.query.filter(or_(
        Notification.recipient_id == user_id,
        Notification.actor_id == user_id,
    )).delete(synchronize_session=False)
    conversation_ids = [row.id for row in Conversation.query.filter(
        or_(Conversation.user_id1 == user_id, Conversation.user_id2 == user_id)
    ).all()]
    message_ids = [row.id for row in Message.query.filter(
        or_(Message.sender_id == user_id, Message.conversation_id.in_(conversation_ids or [-1]))
    ).all()]
    if message_ids:
        MessageRead.query.filter(MessageRead.message_id.in_(message_ids)).delete(synchronize_session=False)
    MessageRead.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    if message_ids:
        Message.query.filter(Message.id.in_(message_ids)).delete(synchronize_session=False)
    if conversation_ids:
        Conversation.query.filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)

    post_ids = [row.id for row in Post.query.filter_by(user_id=user_id).all()]
    if post_ids:
        PostLike.query.filter(PostLike.post_id.in_(post_ids)).delete(synchronize_session=False)
        PostComment.query.filter(PostComment.post_id.in_(post_ids)).delete(synchronize_session=False)
    PostLike.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    PostComment.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    if post_ids:
        Post.query.filter(Post.id.in_(post_ids)).delete(synchronize_session=False)

    reel_ids = [row.id for row in Reels.query.filter_by(user_id=user_id).all()]
    if reel_ids:
        Reels_Likes.query.filter(Reels_Likes.reel_id.in_(reel_ids)).delete(synchronize_session=False)
        Comments.query.filter(Comments.reel_id.in_(reel_ids)).delete(synchronize_session=False)
    Reels_Likes.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Comments.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    if reel_ids:
        Reels.query.filter(Reels.id.in_(reel_ids)).delete(synchronize_session=False)

    story_ids = [row.id for row in Story.query.filter_by(user_id=user_id).all()]
    if story_ids:
        StoryLikes.query.filter(StoryLikes.story_id.in_(story_ids)).delete(synchronize_session=False)
    StoryLikes.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    if story_ids:
        Story.query.filter(Story.id.in_(story_ids)).delete(synchronize_session=False)
    db.session.delete(user)


@bp.before_app_request
def load_loggend_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = UserCreateForm()

    if request.method == 'POST' and form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if not user:
            profile_img_url = None
            image = form.profile_img_url.data

            if image and getattr(image, "filename", ""):
                filename = secure_filename(image.filename)
                image.save(
                    os.path.join(
                        current_app.config['PROFILE_UPLOAD_FOLDER'],
                        filename
                    )
                )
                profile_img_url = f'profile/{filename}'
            user = User(
                profile_img_url=profile_img_url,
                username=form.username.data,
                password_hash=generate_password_hash(form.password_hash.data),
                email=form.email.data,
                name=form.name.data,
                intro=form.intro.data,
                birth=form.birth.data,
                status='active',
                last_activity_at=utc_now_naive(),
                created_at=utc_now_naive(),
                updated_at=utc_now_naive()
            )

            db.session.add(user)
            db.session.commit()

            return redirect(url_for('main.index'))
        else:
            flash('이미 존재하는 사용자입니다.')

    return render_template('auth/signup.html', form=form)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        error = None
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            error = '존재하지 않는 사용자입니다'
        elif not check_password_hash(user.password_hash, form.password.data):
            error = '비밀번호가 올바르지 않습니다'
        elif (
                user.status == 'deletion_pending'
                and user.deletion_requested_at
                and user.deletion_requested_at <= utc_now_naive() - timedelta(days=10)
        ):
            permanently_delete_user(user)
            db.session.commit()
            error = '탈퇴 처리 기간이 지나 계정이 삭제되었습니다.'
        if error is None:
            user.status = 'active'
            user.deletion_requested_at = None
            user.last_activity_at = utc_now_naive()
            user.updated_at = utc_now_naive()
            db.session.commit()
            session.clear()
            login_user(user)
            session['user_id'] = user.id
            session['username'] = user.username
            next_url = request.args.get('next')
            if next_url:
                parsed_next_url = urlparse(next_url)
                if not parsed_next_url.netloc and parsed_next_url.path.startswith('/'):
                    return redirect(next_url)

            return redirect(url_for('main.index'))
        flash(error)
    return render_template('auth/login.html', form=form)


@bp.route('/find_info', methods=['GET', 'POST'])
def find_info():
    from flask_wtf import FlaskForm

    form = FlaskForm()
    found_username = None
    if request.method == 'POST':
        if not form.validate_on_submit():
            flash('요청이 만료되었습니다. 다시 시도해 주세요.')
        else:
            action = request.form.get('action')
            email = request.form.get('email', '').strip()
            user = User.query.filter_by(email=email).first() if email else None

            if action == 'find_username':
                if user:
                    found_username = user.username
                else:
                    flash('입력한 이메일로 가입한 계정을 찾을 수 없습니다.')
            elif action == 'reset_password':
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '')
                password_confirm = request.form.get('password_confirm', '')
                if not username or not email or not password or not password_confirm:
                    flash('아이디, 이메일, 새 비밀번호를 입력해 주세요.')
                elif password != password_confirm:
                    flash('새 비밀번호가 일치하지 않습니다.')
                elif not user or user.username != username:
                    flash('아이디와 이메일이 일치하는 계정을 찾을 수 없습니다.')
                elif check_password_hash(user.password_hash, password):
                    flash('기존 비밀번호와 동일합니다.')
                else:
                    user.password_hash = generate_password_hash(password)
                    user.updated_at = utc_now_naive()
                    db.session.commit()
                    flash('비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.')
            else:
                flash('올바르지 않은 요청입니다.')

    return render_template('auth/find_info.html', form=form, found_username=found_username)


@bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/profile_edit', methods=['GET', 'POST'])
def profile_edit():
    from flask_wtf import FlaskForm

    form = ProfileEditForm()

    if request.method == 'GET':
        form.username.data = g.user.username
        form.name.data = g.user.name
        form.birth.data = g.user.birth
        form.email.data = g.user.email
        form.intro.data = g.user.intro

    if form.validate_on_submit():
        if form.username.data:
            user = User.query.filter(
                User.username == form.username.data,
                User.id != g.user.id
            ).first()

            if user:
                flash('이미 사용 중인 아이디입니다.')
                return redirect(url_for('auth.profile_edit'))

            g.user.username = form.username.data

        if form.name.data:
            g.user.name = form.name.data

        if form.birth.data:
            g.user.birth = form.birth.data

        if form.email.data:
            user = User.query.filter(
                User.email == form.email.data,
                User.id != g.user.id
            ).first()

            if user:
                flash('이미 사용 중인 이메일입니다.')
                return redirect(url_for('auth.profile_edit'))

            g.user.email = form.email.data

        g.user.intro = form.intro.data

        image = form.profile_img_url.data
        if image and getattr(image, 'filename', ''):
            filename = secure_filename(image.filename)
            if not filename:
                flash('사용할 수 없는 파일 이름입니다.')
                return redirect(url_for('auth.profile_edit'))

            image.save(os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], filename))
            g.user.profile_img_url = f'profile/{filename}'

        g.user.updated_at = utc_now_naive()

        db.session.commit()

        flash('회원정보가 수정되었습니다.', 'profile_updated')
        return redirect(url_for('main.index'))

    return render_template(
        'auth/profile_edit.html',
        form=form,
        account_form=FlaskForm()
    )


@bp.route('/mypage')
def mypage():
    from flask_wtf import FlaskForm

    if g.user is None:
        return redirect(url_for('auth.login'))

    profile_user_id = request.args.get('user_id', type=int)
    profile_user = User.query.filter_by(id=profile_user_id).first_or_404() if profile_user_id else g.user
    is_own_profile = profile_user.id == g.user.id

    pair_low_id, pair_high_id = sorted((g.user.id, profile_user.id))
    friendship = None if is_own_profile else Friendship.query.filter_by(
        user_low_id=pair_low_id,
        user_high_id=pair_high_id,
    ).first()

    friends = []
    incoming_requests = []
    outgoing_requests = []
    if is_own_profile:
        accepted_relations = Friendship.query.filter(
            Friendship.status == 'accepted',
            or_(Friendship.user_low_id == g.user.id, Friendship.user_high_id == g.user.id),
        ).all()
        friend_ids = {
            row.user_high_id if row.user_low_id == g.user.id else row.user_low_id
            for row in accepted_relations
        }
        friends = User.query.filter(User.id.in_(friend_ids)).order_by(User.username.asc()).all() if friend_ids else []

        pending_relations = Friendship.query.filter(
            Friendship.status == 'pending',
            or_(Friendship.user_low_id == g.user.id, Friendship.user_high_id == g.user.id),
        ).order_by(Friendship.created_at.desc()).all()
        other_ids = {
            row.user_high_id if row.user_low_id == g.user.id else row.user_low_id
            for row in pending_relations
        }
        pending_users = {row.id: row for row in User.query.filter(User.id.in_(other_ids)).all()} if other_ids else {}
        incoming_requests = [
            (row, pending_users[row.requested_by_id])
            for row in pending_relations
            if row.requested_by_id != g.user.id and row.requested_by_id in pending_users
        ]
        outgoing_requests = [
            (row, pending_users[row.user_high_id if row.user_low_id == g.user.id else row.user_low_id])
            for row in pending_relations
            if row.requested_by_id == g.user.id
            and (row.user_high_id if row.user_low_id == g.user.id else row.user_low_id) in pending_users
        ]

    posts = Post.query.filter_by(user_id=profile_user.id).order_by(Post.created_at.desc()).all()
    reposts = PostRepost.query.filter_by(user_id=profile_user.id).order_by(PostRepost.created_at.desc()).all()
    reels = Reels.query.filter_by(user_id=profile_user.id).order_by(Reels.created_at.desc()).all()
    reel_comments = Comments.query.filter(Comments.reel_id.in_([reel.id for reel in reels])).all() if reels else []
    reel_comments_by_id = {}
    for comment in reel_comments:
        reel_comments_by_id.setdefault(comment.reel_id, []).append(comment)
    reel_comment_users = {user.id: user for user in User.query.filter(
        User.id.in_({comment.user_id for comment in reel_comments})
    ).all()} if reel_comments else {}
    stories = Story.query.filter_by(user_id=profile_user.id).order_by(Story.create_date.desc()).all()

    # account_form은 인스턴스 객체로 전달해야 하므로 괄호 없이 FlaskForm() 전달
    return render_template(
        'auth/mypage.html',
        user=profile_user,
        is_own_profile=is_own_profile,
        friendship=friendship,
        friends=friends,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        posts=posts,
        reposts=reposts,
        reels=reels,
        stories=stories,
        reel_comments_by_id=reel_comments_by_id,
        reel_comment_users=reel_comment_users,
        account_form=FlaskForm()
    )


def _friend_action_form_is_valid():
    from flask_wtf import FlaskForm
    return FlaskForm().validate_on_submit()


def _friend_profile_redirect(user_id):
    return redirect(url_for('auth.mypage', user_id=user_id))


@bp.route('/friend/<int:target_id>/request', methods=['POST'])
def send_friend_request(target_id):
    if not _friend_action_form_is_valid():
        flash('요청이 만료되었습니다. 다시 시도해 주세요.')
        return _friend_profile_redirect(target_id)
    target = User.query.filter_by(id=target_id, status='active').first_or_404()
    if target.id == g.user.id:
        flash('자기 자신에게 친구 요청을 보낼 수 없습니다.')
        return _friend_profile_redirect(target_id)

    low_id, high_id = sorted((g.user.id, target.id))
    friendship = Friendship.query.filter_by(user_low_id=low_id, user_high_id=high_id).first()
    if friendship:
        if friendship.status == 'accepted':
            flash('이미 친구인 회원입니다.')
        elif friendship.requested_by_id == g.user.id:
            flash('이미 친구 요청을 보냈습니다.')
        else:
            flash('상대방이 보낸 친구 요청을 먼저 확인해 주세요.')
        return _friend_profile_redirect(target_id)

    now = utc_now_naive()
    friendship = Friendship(
        user_low_id=low_id,
        user_high_id=high_id,
        requested_by_id=g.user.id,
        status='pending',
        created_at=now,
        updated_at=now,
    )
    db.session.add(friendship)
    db.session.flush()
    notification = Notification(
        recipient_id=target.id,
        actor_id=g.user.id,
        friendship_id=friendship.id,
        type='friend_request',
        is_read=False,
        created_at=now,
    )
    db.session.add(notification)
    db.session.commit()
    from story.events import socketio
    unread_count = Notification.query.filter_by(recipient_id=target.id, is_read=False).count()
    socketio.emit('new_notification', {
        'id': notification.id,
        'type': notification.type,
        'actor_id': g.user.id,
        'actor_username': g.user.username,
        'actor_profile_img_url': g.user.profile_img_url,
        'message': f'{g.user.username}님이 친구 요청을 보냈습니다.',
        'url': url_for('auth.mypage', user_id=g.user.id),
        'created_at': now.isoformat(),
        'unread_count': unread_count,
    }, to=f'user_{target.id}')
    flash('친구 요청을 보냈습니다.')
    return _friend_profile_redirect(target_id)


@bp.route('/friend/<int:target_id>/<action>', methods=['POST'])
def update_friendship(target_id, action):
    if not _friend_action_form_is_valid():
        flash('요청이 만료되었습니다. 다시 시도해 주세요.')
        return _friend_profile_redirect(target_id)
    if action not in {'accept', 'reject', 'cancel', 'remove'}:
        return _friend_profile_redirect(target_id)

    target = User.query.get_or_404(target_id)
    if target.id == g.user.id:
        return _friend_profile_redirect(target_id)
    low_id, high_id = sorted((g.user.id, target.id))
    friendship = Friendship.query.filter_by(user_low_id=low_id, user_high_id=high_id).first()
    if not friendship:
        flash('친구 요청 또는 관계를 찾을 수 없습니다.')
        return _friend_profile_redirect(target_id)

    if action == 'accept' and friendship.status == 'pending' and friendship.requested_by_id == target.id:
        friendship.status = 'accepted'
        friendship.updated_at = utc_now_naive()
        Notification.query.filter_by(friendship_id=friendship.id, recipient_id=g.user.id).update(
            {Notification.is_read: True}, synchronize_session=False
        )
        db.session.commit()
        flash('친구 요청을 수락했습니다.')
    elif action in {'reject', 'cancel'} and friendship.status == 'pending':
        is_incoming = friendship.requested_by_id == target.id
        is_outgoing = friendship.requested_by_id == g.user.id
        if (action == 'reject' and is_incoming) or (action == 'cancel' and is_outgoing):
            Notification.query.filter_by(friendship_id=friendship.id).delete(synchronize_session=False)
            db.session.delete(friendship)
            db.session.commit()
            flash('친구 요청을 정리했습니다.')
        else:
            flash('이 요청을 처리할 권한이 없습니다.')
    elif action == 'remove' and friendship.status == 'accepted':
        Notification.query.filter_by(friendship_id=friendship.id).delete(synchronize_session=False)
        db.session.delete(friendship)
        db.session.commit()
        flash('친구 관계를 삭제했습니다.')
    else:
        flash('현재 상태에서는 해당 작업을 할 수 없습니다.')

    return _friend_profile_redirect(g.user.id if request.form.get('return_to') == 'self' else target.id)


@bp.route('/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    if not _friend_action_form_is_valid():
        return jsonify({'success': False, 'message': '요청이 만료되었습니다.'}), 400
    Notification.query.filter_by(recipient_id=g.user.id, is_read=False).update(
        {Notification.is_read: True}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({'success': True, 'unread_count': 0})


@bp.route('/deactivate', methods=['POST'])
def deactivate():
    from flask_wtf import FlaskForm
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('요청이 만료되었습니다. 다시 시도해 주세요.')
        return redirect(url_for('auth.profile_edit'))
    if g.user is None:
        return redirect(url_for('auth.login'))
    g.user.status = 'inactive'
    g.user.updated_at = utc_now_naive()
    db.session.commit()
    logout_user()
    session.clear()
    flash('계정이 비활성화되었습니다. 다시 로그인하면 활성화됩니다.')
    return redirect(url_for('auth.login'))


@bp.route('/delete_request', methods=['POST'])
def request_account_deletion():
    from flask_wtf import FlaskForm
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('요청이 만료되었습니다. 다시 시도해 주세요.')
        return redirect(url_for('auth.profile_edit'))
    if g.user is None:
        return redirect(url_for('auth.login'))
    g.user.status = 'deletion_pending'
    g.user.deletion_requested_at = utc_now_naive()
    g.user.updated_at = utc_now_naive()
    db.session.commit()
    logout_user()
    session.clear()
    flash('탈퇴가 신청되었습니다. 10일 이내에 다시 로그인하면 탈퇴 신청이 취소됩니다.')
    return redirect(url_for('auth.login'))
