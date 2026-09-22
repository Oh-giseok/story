from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField,TextAreaField,PasswordField,EmailField,SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email

#회원가입
class UserCreateForm(FlaskForm):
    username = StringField('ID', validators=[DataRequired(), Length(min=2, max=20)])
    password_hash1 = PasswordField('비밀번호',validators=[DataRequired(), EqualTo('password_hash2',message='비밀번호가 일치하지 않습니다')])
    password_hash2 = PasswordField('비밀번호 재입력',validators=[DataRequired()])
    email = EmailField('이메일',validators=[DataRequired(),Email()])
    name = StringField('이름', validators=[DataRequired()])
    birth = StringField('생년월일', validators=[DataRequired()])
    submit = SubmitField('회원가입')
