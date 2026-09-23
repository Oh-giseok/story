import os

BASE_DIR = os.path.dirname(__file__)

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'story.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = 'dev'

SQLALCHEMY_DATABASE_URI = 'sqlite:///story.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

SECRET_KEY = 'your-secret-key'