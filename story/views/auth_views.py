from flask import Blueprint,request,redirect,url_for,flash,render_template, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from story import db
from story.forms import UserCreateForm,UserLoginForm
from story.models import User

bp =Blueprint('auth', __name__,url_prefix='/auth')

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = UserCreateForm()

    if request.method == 'POST' and form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if not user:
            user = User(
                username=form.username.data,
                password_hash=generate_password_hash(form.password_hash.data),
                email=form.email.data,
                name=form.name.data,
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
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash(error)
    return render_template('auth/login.html',form=form)