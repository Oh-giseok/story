from flask import Blueprint,request,redirect,url_for,flash,render_template, session, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from urllib.parse import urlparse
import os
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user

from story import db
from story.forms import UserCreateForm,UserLoginForm,ProfileEditForm
from story.models import User, Post, Reels, Story

bp =Blueprint('auth', __name__,url_prefix='/auth')

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

            if image and getattr(image,"filename",""):
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
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            db.session.add(user)
            db.session.commit()

            return redirect(url_for('index'))
        else:
            flash('이미 존재하는 사용자입니다.')

    return render_template('auth/signup.html', form=form)

@bp.route('/login',methods=['GET','POST'])
def login():
    form =  UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        error = None
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            error = '존재하지 않는 사용자입니다'
        elif not check_password_hash(user.password_hash, form.password.data):
            error = '비밀번호가 올바르지 않습니다'
        if error is None:
            session.clear()
            login_user(user)
            session['user_id'] = user.id
            session['username'] = user.username
            next_url = request.args.get('next')
            if next_url:
                parsed_next_url = urlparse(next_url)
                if not parsed_next_url.netloc and parsed_next_url.path.startswith('/'):
                    return redirect(next_url)
            return redirect(url_for('index'))
        flash(error)
    return render_template('auth/login.html',form=form)

@bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# 회원정보 수정
@bp.route('/profile_edit', methods=['GET', 'POST'])
def profile_edit():

    form = ProfileEditForm()

    # 처음 페이지에 들어왔을 때 기존 정보 표시
    if request.method == 'GET':
        form.username.data = g.user.username
        form.name.data = g.user.name
        form.birth.data = g.user.birth
        form.email.data = g.user.email
        form.intro.data = g.user.intro

    if form.validate_on_submit():

        # 입력한 값만 수정
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

        g.user.updated_at = datetime.now()

        db.session.commit()

        flash('회원정보가 수정되었습니다.')

        return redirect(url_for('post._list'))

    return render_template(
        'auth/profile_edit.html',
        form=form
    )

#마이페이지
@bp.route('/mypage')
def mypage():
    if g.user is None:
        return redirect(url_for('auth.login'))

    posts = Post.query.filter_by(user_id=g.user.id).order_by(Post.created_at.desc()).all()
    reels = Reels.query.filter_by(user_id=g.user.id).order_by(Reels.created_at.desc()).all()
    stories = Story.query.filter_by(user_id=g.user.id).order_by(Story.create_date.desc()).all()

    return render_template(
        'auth/mypage.html', user=g.user, posts=posts, reels=reels, stories=stories
    )
