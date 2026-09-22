#forms.py
from flask_wtf import FlaskForm
from wtforms import FileField, TextAreaField, SubmitField
from flask_wtf.file import FileAllowed
from wtforms.validators import DataRequired


class ReelsForm(FlaskForm):
    video_url = FileField('영상 선택', validators=[DataRequired(),
    FileAllowed(['mp4', 'mov', 'webm'], '영상 파일만 업로드할 수 있습니다.')])
    thumbnail = FileField("썸네일 선택", validators=[DataRequired()])
    caption = TextAreaField('캡션', validators=[DataRequired()])
    submit = SubmitField('업로드')