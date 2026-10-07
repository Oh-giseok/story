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

# 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 전체 프로젝트 복사
COPY . .

# Flask 환경변수 설정
ENV FLASK_APP=story:create_app
ENV FLASK_ENV=production

# 포트 오픈
EXPOSE 5000

# 프로덕션 환경(Gunicorn + Eventlet 워커)을 이용해 실행
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "story:create_app()"]