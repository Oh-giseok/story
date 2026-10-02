from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField,TextAreaField,PasswordField,EmailField,SubmitField, FileField
from wtforms.validators import DataRequired, Length, EqualTo, Email
from flask_wtf.file import FileAllowed

#회원가입
class UserCreateForm(FlaskForm):
    profile_img_url = FileField('프로필 이미지', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'],'이미지파일만 업로드할 수 있습니다.')])
    username = StringField('ID', validators=[DataRequired(), Length(min=2, max=20)])
    password_hash = PasswordField('비밀번호',validators=[DataRequired(), EqualTo('password_hash2',message='비밀번호가 일치하지 않습니다')])
    password_hash2 = PasswordField('비밀번호 재입력',validators=[DataRequired()])
    email = EmailField('이메일',validators=[DataRequired(),Email()])
    name = StringField('이름', validators=[DataRequired()])
    intro = TextAreaField('자기소개',validators=[Length(max=500)])
    birth = StringField('생년월일', validators=[DataRequired()])
    submit = SubmitField('회원가입')

#로그인
class UserLoginForm(FlaskForm):
    # Keep the login username limits aligned with UserCreateForm.
    username = StringField('아이디',validators=[DataRequired(),Length(min=2,max=20)])
    password = PasswordField('비밀번호',validators=[DataRequired()])
    submit = SubmitField('로그인')

# 릴스 생성 폼
class ReelsForm(FlaskForm):
    video_url = FileField('영상 선택', validators=[DataRequired(),
    FileAllowed(['mp4', 'mov', 'webm'], '영상 파일만 업로드할 수 있습니다.')])
    thumbnail = FileField("썸네일 선택", validators=[DataRequired()])
    caption = TextAreaField('캡션', validators=[DataRequired()])
    submit = SubmitField('업로드')

class ReelsEditForm(FlaskForm):
    video_url = FileField(
        '영상',
        validators=[
            FileAllowed(['mp4', 'mov', 'webm'], '영상 파일만 업로드할 수 있습니다.')
        ],
        render_kw={'accept': '.mp4,.mov,.webm'}
    )

    thumbnail = FileField(
        '썸네일',
        validators=[
            FileAllowed(
                ['jpg', 'jpeg', 'png', 'webp'],
                '이미지 파일만 업로드할 수 있습니다.'
            )
        ],
        render_kw={'accept': '.jpg,.jpeg,.png,.webp'}
    )

    caption = TextAreaField(
        '캡션',
        validators=[DataRequired()]
    )

    submit = SubmitField('수정 완료')


class CommentsForm(FlaskForm):
    content = TextAreaField(
        '댓글',
        validators=[DataRequired()]
    )

    submit = SubmitField('등록')
#회원정보수정
class ProfileEditForm(FlaskForm):
    username = StringField('아이디')
    name = StringField('이름')
    birth = StringField('생년월일')
    email = StringField('이메일')
    profile_img_url = FileField('프로필 이미지', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], '이미지파일만 업로드할 수 있습니다.')])
    intro = TextAreaField('자기소개', validators=[Length(max=500)])
    submit = SubmitField('저장하기')

# 스토리 생성 폼
class StoryForm(FlaskForm):
    image = FileField('스토리 이미지', validators=[DataRequired()])
    caption = TextAreaField('스토리 문구')
    submit = SubmitField('업로드')
