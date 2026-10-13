# STORY

사진과 짧은 영상으로 일상을 공유하고 사람들과 소통하는 SNS 웹 애플리케이션입니다. 게시물과 댓글, 릴스, 스토리, 친구 기능, 알림과 1:1 실시간 채팅을 제공합니다.

## 주요 기능

- 회원가입, 로그인, 프로필 및 마이페이지
- 사진 게시물 작성, 수정, 삭제, 좋아요, 댓글, 재공유
- 짧은 영상 릴스 및 기간 한정 스토리
- 친구 요청, 활동 알림, 접속 상태
- Socket.IO 기반 실시간 1:1 채팅
- Supabase Storage 연동 업로드 및 로컬 파일 저장 지원

## 기술 구성

- Backend: Python 3.12, Flask, Flask-SocketIO
- Frontend: HTML, CSS, JavaScript, Jinja2
- Database: SQLAlchemy, SQLite 또는 PostgreSQL
- 실시간 메시지 큐: Redis (선택)
- 미디어 저장소: 로컬 파일 시스템 또는 Supabase Storage
- 배포: Docker, Gunicorn, Render 설정 제공

## Docker 이미지 빌드 및 실행

저장소 루트에서 이미지를 빌드합니다.

```bash
docker build -t story:latest .
```

프로젝트 루트에 `.env` 파일을 준비한 뒤 실행합니다.

```bash
docker run -d --name story \
  --env-file .env \
  -p 5001:5000 \
  -v story-instance:/app/instance \
  -v story-photo:/app/story/static/photo \
  -v story-profile:/app/story/static/profile \
  -v story-reels:/app/story/static/reels_uploads \
  story:latest
```

Windows 명령 프롬프트에서는 한 줄로 실행할 수 있습니다.

```bat
docker run -d --name story --env-file .env -p 5000:5000 -v story-instance:/app/instance -v story-photo:/app/story/static/photo -v story-profile:/app/story/static/profile -v story-reels:/app/story/static/reels_uploads story:latest
```

접속 주소: [http://localhost:5000/](http://localhost:5000/)

## 환경변수

| 이름 | 용도 | 필수 여부 |
| --- | --- | --- |
| `SECRET_KEY` | 세션 및 CSRF 보호용 비밀키 | 배포 환경에서 필수 |
| `DATABASE_URL` | PostgreSQL 등 외부 데이터베이스 연결 주소. 미설정 시 SQLite 사용 | 선택 |
| `REDIS_URL` | Socket.IO 메시지 큐 연결 주소 | 선택 |
| `SUPABASE_URL` | Supabase 프로젝트 URL | 외부 미디어 저장 사용 시 필수 |
| `SUPABASE_SECRET_KEY` | Supabase Storage 서버 측 인증 키 | 외부 미디어 저장 사용 시 필수 |
| `SUPABASE_STORAGE_BUCKET` | Storage 버킷 이름. 기본값은 `story-media` | 선택 |

`SUPABASE_SECRET_KEY` 대신 `SUPABASE_SERVICE_ROLE_KEY`를 사용할 수도 있습니다. 키와 비밀번호는 저장소나 Docker Hub 소개글에 올리지 말고 `.env` 또는 배포 플랫폼의 비밀 환경변수로 관리하세요.

## 데이터 및 업로드 저장 안내

기본 설정은 SQLite와 컨테이너 내부 파일 시스템을 사용합니다. 위 실행 예시의 Docker 볼륨을 사용하면 데이터베이스와 로컬 업로드 파일을 컨테이너 교체 후에도 보존할 수 있습니다. 호스팅 플랫폼에서 영구 볼륨을 제공하지 않는 경우에는 PostgreSQL과 Supabase Storage 같은 외부 영구 저장소를 설정하세요.

## 프로젝트 저장소

[GitHub 저장소](https://github.com/Oh-giseok/story)