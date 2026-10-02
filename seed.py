"""Create repeatable demo accounts and their connected content.

Run from the repository root with ``.venv\\Scripts\\python seed.py``.
All demo accounts use the password ``1234``. Existing non-demo rows are kept.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from werkzeug.security import generate_password_hash

from story import create_app, db
from story.models import (
    Comments, Post, PostComment, PostLike, Reels, Reels_Likes, Story, User,
)

PASSWORD = "1234"
TARGET_PER_TYPE = 5
PEOPLE = [
    ("mori_cafe", "김서윤", "카페와 디저트 찾아다니는 기록", "카페", "☕"),
    ("film_jun", "박준호", "영화와 전시를 즐기는 주말", "영화", "🎬"),
    ("run_haru", "이하루", "퇴근 후 러닝을 꾸준히", "러닝", "🏃"),
    ("trip_min", "최민재", "시간만 나면 떠나는 여행", "여행", "✈"),
    ("plant_nana", "정나은", "집에서 작은 정글 만드는 중", "식물", "🌿"),
    ("food_tae", "강태윤", "맛있는 건 일단 사진부터", "요리", "🍜"),
    ("draw_jiu", "윤지우", "매일 조금씩 그림 그리기", "그림", "🎨"),
    ("music_ian", "한이안", "플레이리스트와 공연 기록", "음악", "🎧"),
    ("fashion_roe", "서로운", "깔끔한 데일리룩 기록", "패션", "👟"),
    ("pet_dodo", "오도현", "강아지 도도와 보내는 하루", "반려견", "🐶"),
]
PALETTES = [(89, 91, 173), (164, 99, 75), (69, 143, 111), (194, 132, 63),
            (76, 132, 83), (65, 119, 192), (150, 91, 160), (176, 97, 120),
            (94, 112, 154), (152, 125, 73)]


def asset_dirs(root: Path):
    dirs = {name: root / "static" / "seed_media" / name for name in ("posts", "stories", "profiles")}
    # Reels are served by the uploaded_file route from app.config['UPLOAD_FOLDER'].
    dirs["videos"] = root / "reels_uploads" / "videos"
    dirs["thumbs"] = root / "reels_uploads" / "thumbnails"
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def create_card(path: Path, username: str, name: str, topic: str, index: int, kind: str, color):
    """Write a unique SVG card, keeping media grouped by content type."""
    if path.exists():
        return
    hue = (index * 29 + len(username) * 11) % 360
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1100" viewBox="0 0 900 1100">
<defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="hsl({hue},55%,78%)"/><stop offset="1" stop-color="hsl({(hue+65)%360},48%,38%)"/></linearGradient></defs>
<rect width="900" height="1100" fill="url(#g)"/><circle cx="720" cy="260" r="190" fill="white" opacity=".18"/>
<path d="M0 800 Q230 630 450 820 T900 760 V1100 H0Z" fill="white" opacity=".22"/>
<text x="72" y="120" fill="white" font-size="34" font-family="sans-serif">5TORY · {kind.upper()} #{index:02}</text>
<text x="72" y="670" fill="white" font-size="92" font-weight="700" font-family="sans-serif">{topic}</text>
<text x="76" y="755" fill="white" font-size="40" font-family="sans-serif">{name} · @{username}</text>
<text x="76" y="1010" fill="white" font-size="30" font-family="sans-serif">오늘의 {topic} 기록</text></svg>'''
    path.write_text(svg, encoding="utf-8")


def create_reel(path: Path, username: str, topic: str, index: int, color):
    """Generate a short topic-titled MP4 so each reel has a real video asset."""
    if path.exists() and path.stat().st_size > 1000:
        return
    width, height, fps, frames = 360, 640, 15, 45
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"MP4 writer unavailable: {path}")
    for frame_no in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        t = frame_no / frames
        for y in range(height):
            blend = y / height
            frame[y, :] = [int(color[0] * (1-blend) + 38 * blend),
                           int(color[1] * (1-blend) + 44 * blend),
                           int(color[2] * (1-blend) + 87 * blend)]
        x = int(180 + 78 * math.sin(t * math.tau))
        cv2.circle(frame, (x, 255), 66, (235, 238, 244), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, 255), 48, color, -1, cv2.LINE_AA)
        cv2.putText(frame, topic, (28, 410), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"@{username}  /  REEL {index:02}", (28, 458), cv2.FONT_HERSHEY_SIMPLEX, .43, (235,235,235), 1, cv2.LINE_AA)
        cv2.putText(frame, "5TORY DAILY", (28, 570), cv2.FONT_HERSHEY_SIMPLEX, .55, (225,225,225), 1, cv2.LINE_AA)
        writer.write(frame)
    writer.release()


def create_thumbnail(path: Path, username: str, topic: str, index: int, color):
    if path.exists():
        return
    canvas = np.zeros((640, 360, 3), dtype=np.uint8)
    canvas[:] = color
    cv2.circle(canvas, (180, 225), 108, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, (180, 225), 91, color, -1, cv2.LINE_AA)
    cv2.putText(canvas, topic, (25, 420), cv2.FONT_HERSHEY_SIMPLEX, .9, (255,255,255), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"@{username} REEL {index:02}", (25, 470), cv2.FONT_HERSHEY_SIMPLEX, .43, (245,245,245), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])


def ensure_assets(root: Path):
    dirs = asset_dirs(root)
    for i, (username, name, _, topic, _) in enumerate(PEOPLE):
        create_card(dirs["profiles"] / f"{username}.svg", username, name, topic, 0, "profile", PALETTES[i])
        for index in range(1, TARGET_PER_TYPE + 1):
            create_card(dirs["posts"] / f"{username}_post_{index}.svg", username, name, topic, index, "post", PALETTES[i])
            create_card(dirs["stories"] / f"{username}_story_{index}.svg", username, name, topic, index, "story", PALETTES[i])
            create_reel(dirs["videos"] / f"{username}_reel_{index}.mp4", username, topic, index, PALETTES[i])
            create_thumbnail(dirs["thumbs"] / f"{username}_reel_{index}.jpg", username, topic, index, PALETTES[i])
    return dirs


def seed():
    app = create_app()
    with app.app_context():
        dirs = ensure_assets(Path(app.root_path))
        seed_users = []
        for i, (username, name, intro, topic, _) in enumerate(PEOPLE):
            login_name = f"seed_{username}"
            user = User.query.filter_by(username=login_name).first()
            if user is None:
                user = User(username=login_name, email=f"{login_name}@5tory.local")
                db.session.add(user)
            user.password_hash = generate_password_hash(PASSWORD)
            user.name, user.intro = name, f"{intro} · 관심사: {topic}"
            user.profile_img_url = f"seed_media/profiles/{username}.svg"
            user.birth = f"199{(i % 9) + 1}-0{(i % 8) + 1}-15"
            user.status = "active"
            seed_users.append((i, username, topic, user))
        db.session.flush()

        new_posts, new_reels, new_stories = [], [], []
        now = datetime.utcnow()
        for i, username, topic, user in seed_users:
            existing_posts = Post.query.filter_by(user_id=user.id).count()
            for j in range(existing_posts, TARGET_PER_TYPE):
                created = now - timedelta(days=i + j + 1, hours=j)
                item = Post(user_id=user.id, caption=f"{topic} 기록 #{j+1} — 오늘의 작은 순간을 담았어요.",
                            media_url=f"/static/seed_media/posts/{username}_post_{j+1}.svg",
                            thumbnail_url=f"/static/seed_media/posts/{username}_post_{j+1}.svg",
                            created_at=created, updated_at=created)
                db.session.add(item); new_posts.append(item)
            existing_reels = Reels.query.filter_by(user_id=user.id).count()
            for j in range(existing_reels, TARGET_PER_TYPE):
                created = now - timedelta(days=i + j + 1, hours=j)
                item = Reels(user_id=user.id, video_url=f"{username}_reel_{j+1}.mp4",
                             thumbnail_url=f"{username}_reel_{j+1}.jpg",
                             caption=f"{topic} 릴스 #{j+1}", duration=3.0,
                             created_at=created, updated_at=created)
                db.session.add(item); new_reels.append(item)
            existing_stories = Story.query.filter_by(user_id=user.id).count()
            for j in range(existing_stories, TARGET_PER_TYPE):
                # Recent and unexpired so stories appear immediately in the app.
                created = now - timedelta(minutes=(TARGET_PER_TYPE-j) * 8)
                db.session.add(Story(user_id=user.id,
                    media_url=f"/static/seed_media/stories/{username}_story_{j+1}.svg",
                    thumbnail_url=f"/static/seed_media/stories/{username}_story_{j+1}.svg",
                    caption=f"{topic} 스토리 #{j+1}", create_date=created,
                    expires_at=created + timedelta(hours=24)))
                new_stories.append(user.id)

        db.session.flush()
        # Connect demo users to one another through likes and comments.
        demo_ids = [u.id for _, _, _, u in seed_users]
        for post in new_posts:
            for liker_id in demo_ids:
                if liker_id != post.user_id and PostLike.query.filter_by(post_id=post.id, user_id=liker_id).first() is None:
                    db.session.add(PostLike(post_id=post.id, user_id=liker_id))
                    break
            commenter = next(uid for uid in demo_ids if uid != post.user_id)
            db.session.add(PostComment(post_id=post.id, user_id=commenter, content="멋진 기록이야!"))
        for reel in new_reels:
            commenter = next(uid for uid in demo_ids if uid != reel.user_id)
            db.session.add(Reels_Likes(reel_id=reel.id, user_id=commenter))
            db.session.add(Comments(reel_id=reel.id, user_id=commenter, content="영상 분위기 좋다!"))
        db.session.commit()

        print("시드 생성 완료: demo 계정 10개, 계정별 게시물/릴스/스토리 최소 5개")
        print("계정: seed_mori_cafe 등 / 공통 비밀번호: 1234")
        print(f"이번 실행 추가: 게시물 {len(new_posts)}, 릴스 {len(new_reels)}, 스토리 {len(new_stories)}")


if __name__ == "__main__":
    seed()
