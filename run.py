from story import create_app
from story.models import db
from story.events import socketio

app = create_app()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5001, debug=True)