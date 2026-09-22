from flask import Blueprint,request,redirect,url_for,flash,render_template
from werkzeug.security import generate_password_hash

from story import db
from story.forms import UserCreateForm
from story.models import User

bp =Blueprint('auth', __name__,url_prefix='/auth')

@bp.route('/signup',methods=['GET','POST'])
def signup():
    form = UserCreateForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            user = User(username=form.username.data,
                        password_hash=form.passhash_hash1.data,
                        email=form.email.data,
                        name=form.name.data,
                        birth=form.birth.data,
            )
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('main.index'))
        else:
            flash('이미 존재하는 사용자입니다.')
    return render_template('auth/signup.html',form=form)