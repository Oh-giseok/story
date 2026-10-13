# 베이스 이미지 선택
FROM python:3.12-slim

# 시간대 설정 (KST)
ENV TZ=Asia/Seoul
RUN apt-get update && apt-get install -y \
    tzdata \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 생성 및 이동
WORKDIR /app
RUN mkdir -p /app/instance

# Render build logs can identify this Dockerfile revision independently of the
# service's configured start command. This marker is intentionally static.
ARG STORY_GTHREAD_BUILD_ID=story-gthread-20261008-v1
ENV STORY_GTHREAD_BUILD_ID=${STORY_GTHREAD_BUILD_ID}
RUN printf '%s\n' '=== STORY DOCKER BUILD: GTHREAD VERSION ===' \
    "=== STORY DOCKER BUILD ID: ${STORY_GTHREAD_BUILD_ID} ==="

# 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fail the image build if the selected threaded Socket.IO/Gunicorn stack is incomplete.
RUN printf '%s\n' '=== VERIFY GTHREAD / SOCKET.IO THREADING STACK ===' \
    && python -m pip show gunicorn \
    && python -m pip show simple-websocket \
    && python -c "import importlib.util, flask_socketio, simple_websocket, gunicorn; from gunicorn.workers.gthread import ThreadWorker; assert importlib.util.find_spec('eventlet') is None, 'eventlet must not be installed'; print('Gunicorn', gunicorn.__version__, 'gthread worker available; eventlet intentionally absent')"

# 전체 프로젝트 복사
COPY . .

# Flask 환경변수 설정
ENV FLASK_APP=story:create_app
ENV FLASK_ENV=production

# 포트 오픈
EXPOSE 5000

# Socket.IO runs in threading mode; gthread supports polling and WebSocket via simple-websocket.
# Render supplies PORT. The fallback keeps local Docker runs convenient.
CMD ["sh", "-c", "echo \"=== STORY CONTAINER START: ${STORY_GTHREAD_BUILD_ID:-unset} ===\"; echo \"=== GUNICORN CMD: gunicorn --worker-class gthread --workers 1 --threads 100 --bind 0.0.0.0:${PORT:-5000} story:create_app() ===\"; exec gunicorn --worker-class gthread --workers 1 --threads 100 --bind 0.0.0.0:${PORT:-5000} 'story:create_app()'"]
