from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField,TextAreaField,PasswordField,EmailField,SubmitField, FileField
from wtforms.validators import DataRequired, Length, EqualTo, Email
from flask_wtf.file import FileAllowed
#회원가입
class UserCreateForm(FlaskForm):
    username = StringField('ID', validators=[DataRequired(), Length(min=2, max=20)])
    password_hash = PasswordField('비밀번호',validators=[DataRequired(), EqualTo('password_hash2',message='비밀번호가 일치하지 않습니다')])
    password_hash2 = PasswordField('비밀번호 재입력',validators=[DataRequired()])
    email = EmailField('이메일',validators=[DataRequired(),Email()])
    name = StringField('이름', validators=[DataRequired()])
    birth = StringField('생년월일', validators=[DataRequired()])
    submit = SubmitField('회원가입')

#로그인
class UserLoginForm(FlaskForm):
    username = StringField('아이디',validators=[DataRequired(),Length(min=3,max=25)])
    password = PasswordField('비밀번호',validators=[DataRequired()])
    submit = SubmitField('로그인')

# 릴스 생성 폼
class ReelsForm(FlaskForm):
    video_url = FileField('영상 선택', validators=[DataRequired(),
    FileAllowed(['mp4', 'mov', 'webm'], '영상 파일만 업로드할 수 있습니다.')])
    thumbnail = FileField("썸네일 선택", validators=[DataRequired()])
    caption = TextAreaField('캡션', validators=[DataRequired()])
    submit = SubmitField('업로드')