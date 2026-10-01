"""
5tory development seed data

IMPORTANT:
- This script ONLY INSERTS seed records. It never deletes or updates existing rows.
- Seed users use password: 1234 (stored as a password hash).
- Re-running the script skips any seed username that already exists.
- Run from the Flask project root: python seed.py
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

try:
    from story import create_app, db
except ImportError as exc:
    raise SystemExit(
        "story.create_app를 불러오지 못했습니다. seed.py를 Flask 프로젝트 루트에 두고 실행하세요."
    ) from exc

from story.models import (
    User, Post, PostLike, PostComment,
    Reels, Reels_Likes, Comments,
    Story,
)

SEED_PREFIX = "seed_"
PASSWORD = "1234"
RANDOM_SEED = 5_010_2026

USERS = [
    {"username":"mori_cafe","name":"김서윤","intro":"카페와 디저트 찾아다니는 기록 ☕️","interest":"커피 · 베이커리 · 사진","gender":"여"},
    {"username":"film_jun","name":"박준호","intro":"주말마다 영화관과 전시를 돌아다녀요 🎬","interest":"영화 · 전시 · 책","gender":"남"},
    {"username":"run_haru","name":"이하루","intro":"퇴근 후 러닝 5km를 꾸준히! 🏃","interest":"러닝 · 운동 · 건강","gender":"여"},
    {"username":"trip_min","name":"최민재","intro":"시간만 나면 여행 계획부터 세우는 사람 ✈️","interest":"여행 · 풍경 · 맛집","gender":"남"},
    {"username":"plant_nana","name":"정나은","intro":"집에서 작은 정글 만드는 중 🌿","interest":"식물 · 인테리어 · 집꾸미기","gender":"여"},
    {"username":"food_tae","name":"강태윤","intro":"맛있는 건 일단 사진부터 📷","interest":"맛집 · 요리 · 야식","gender":"남"},
    {"username":"draw_jiu","name":"윤지우","intro":"매일 조금씩 그림 그리는 취미생활 🎨","interest":"그림 · 디자인 · 드로잉","gender":"여"},
    {"username":"music_ian","name":"한이안","intro":"플레이리스트 만드는 걸 좋아합니다 🎧","interest":"음악 · 공연 · 기타","gender":"남"},
    {"username":"fashion_roe","name":"서로운","intro":"깔끔한 데일리룩과 소소한 쇼핑 👟","interest":"패션 · 쇼핑 · 일상","gender":"여"},
    {"username":"pet_dodo","name":"오도현","intro":"강아지 도도랑 사는 평범한 하루 🐶","interest":"반려견 · 산책 · 일상","gender":"남"},
]

INTEREST_POSTS = [
    ['아침에 발견한 작은 카페','오늘의 라떼는 성공','퇴근 후 디저트 한 접시','주말 카페 투어','빵 냄새에 이끌려 들어간 곳','조용한 카페에서 보낸 오후'],
    ['이번 주에 본 영화','전시에서 마음에 남은 장면','영화관 가는 날','주말 독서 기록','좋았던 영화 OST','비 오는 날엔 영화 한 편'],
    ['오늘도 5km 완료','러닝 전에 가볍게 스트레칭','운동 후 먹는 저녁','새 러닝 코스 발견','아침 러닝 성공','천천히 오래 달리기'],
    ['주말 여행 준비','기차 타고 떠나는 날','처음 가본 동네','여행 중 만난 풍경','여행지 맛집 기록','다음 여행지는 어디로'],
    ['오늘의 초록이','새 화분 들이기','햇빛 좋은 창가','식물 잎 닦는 날','작은 집 꾸미기','방 분위기 바꾸기'],
    ['오늘의 점심','퇴근 후 맛집','집에서 만든 한 끼','새로 찾은 분식집','야식은 못 참지','주말 브런치'],
    ['오늘의 드로잉','색연필 연습','낙서에서 시작한 그림','카페에서 그림 그리기','새 스케치북 시작','작업실 정리'],
    ['오늘의 플레이리스트','기타 연습 20분','공연 다녀온 날','퇴근길에 듣는 노래','새로운 앨범 발견','밤에 듣기 좋은 곡'],
    ['오늘의 데일리룩','운동화 하나 장만','무채색 코디','가볍게 쇼핑한 날','출근룩 기록','주말 캐주얼'],
    ['도도 산책 완료','강아지 낮잠 시간','새 장난감 테스트','공원에서 뛰어놀기','도도와 주말 보내기','산책 중 만난 친구'],
]

POST_COUNTS = [5,6,4,7,5,6,4,5,6,5]
REEL_COUNTS = [3,4,2,5,3,4,2,3,4,3]
STORY_COUNTS = [3,4,3,5,3,4,3,4,3,4]

POST_COMMENTS = [
    "분위기 너무 좋다!", "여기 어디야? 저장해둘래.", "사진만 봐도 힐링된다.",
    "다음에 나도 같이 가고 싶어.", "이 취향 너무 좋다 ㅋㅋ", "진짜 잘 찍었다.",
    "나도 요즘 이거 관심 있어!", "오늘도 좋은 기록이다."
]
REEL_COMMENTS = [
    "영상 분위기 좋다!", "이거 계속 보게 되네 ㅋㅋ", "다음 편도 기대된다.",
    "아이디어 좋다.", "음악이랑 잘 어울린다.", "짧은데 임팩트 있다."
]


def project_path(app, *parts):
    return Path(app.root_path).joinpath(*parts)


def static_url(*parts):
    return "/static/" + "/".join(parts)


def ensure_assets(app):
    """Verify bundled seed assets exist in the project after extraction/copy."""
    required = [
        project_path(app, "static", "seed_media", "profiles"),
        project_path(app, "static", "seed_media", "posts"),
        project_path(app, "static", "seed_media", "stories"),
        project_path(app, "reels_uploads", "videos"),
        project_path(app, "reels_uploads", "thumbnails"),
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("시드 이미지/영상 폴더가 없습니다:\n" + "\n".join(missing))


def make_comment_text(pool, user_idx, item_idx):
    return pool[(user_idx * 3 + item_idx) % len(pool)]


def seed():
    random.seed(RANDOM_SEED)
    app = create_app()
    with app.app_context():
        ensure_assets(app)

        # Existing DB data is NEVER deleted or modified.
        created_users = []
        skipped = []
        for i, data in enumerate(USERS):
            username = SEED_PREFIX + data["username"]
            existing = User.query.filter_by(username=username).first()
            if existing:
                skipped.append(username)
                continue
            user = User(
                username=username,
                password_hash=generate_password_hash(PASSWORD),
                email=f"{username}@seed.5tory.local",
                name=data["name"],
                intro=data["intro"],
                profile_img_url=f"seed_media/profiles/{data['username']}.svg",
                birth=f"199{(i % 9) + 1}-0{(i % 8) + 1}-1{(i % 8) + 1}",
                status="active",
                last_activity_at=datetime.utcnow(),
            )
            db.session.add(user)
            created_users.append((i, user))

        if not created_users:
            print("이미 모든 seed 사용자가 존재합니다. 기존 DB는 변경하지 않았습니다.")
            if skipped:
                print("건너뜀:", ", ".join(skipped))
            return

        db.session.flush()

        all_users = [u for _, u in created_users]
        posts = []
        reels = []
        stories = []

        for ui, user in created_users:
            uname = USERS[ui]["username"]
            interest = USERS[ui]["interest"]

            for j in range(POST_COUNTS[ui]):
                title = INTEREST_POSTS[ui][j % len(INTEREST_POSTS[ui])]
                images = [static_url("seed_media", "posts", f"{uname}_post_{j+1}.svg")]
                if (j + ui) % 4 == 0:
                    images.append(static_url("seed_media", "posts", f"{uname}_post_{j+1}_2.svg"))
                created = datetime.utcnow() - timedelta(days=(ui * 2 + j + 1), hours=j * 2)
                posts.append(Post(
                    user_id=user.id,
                    caption=f"{title} · {interest}. 오늘의 작은 기록을 남겨봅니다.",
                    media_url=",".join(images),
                    thumbnail_url=images[0],
                    created_at=created,
                    updated_at=created,
                ))

            for j in range(REEL_COUNTS[ui]):
                base = f"{uname}_reel_{j+1}"
                reels.append(Reels(
                    user_id=user.id,
                    video_url=f"{base}.mp4",
                    thumbnail_url=f"{base}.jpg",
                    caption=f"{INTEREST_POSTS[ui][j % len(INTEREST_POSTS[ui])]} — {interest}",
                    duration=2.5 + ((ui + j) % 4) * 0.5,
                    created_at=datetime.utcnow() - timedelta(days=(ui + j + 1), hours=j),
                    updated_at=datetime.utcnow() - timedelta(days=(ui + j + 1), hours=j),
                ))

            for j in range(STORY_COUNTS[ui]):
                created = datetime.utcnow() - timedelta(hours=(j + 1) * 3)
                stories.append(Story(
                    user_id=user.id,
                    media_url=static_url("seed_media", "stories", f"{uname}_story_{j+1}.svg"),
                    thumbnail_url=static_url("seed_media", "stories", f"{uname}_story_{j+1}.svg"),
                    caption=f"오늘의 스토리 · {interest}",
                    create_date=created,
                    expires_at=created + timedelta(hours=24),
                ))

        db.session.add_all(posts + reels + stories)
        db.session.flush()

        # Post likes/comments: only among the 10 newly-created seed users.
        for post in posts:
            possible = [u for u in all_users if u.id != post.user_id]
            random.shuffle(possible)
            for liker in possible[:random.randint(2, min(7, len(possible)))]:
                db.session.add(PostLike(post_id=post.id, user_id=liker.id))
            for ci in range(random.randint(1, 4)):
                commenter = possible[ci % len(possible)]
                db.session.add(PostComment(
                    post_id=post.id,
                    user_id=commenter.id,
                    content=make_comment_text(POST_COMMENTS, commenter.id, ci),
                    created_at=post.created_at + timedelta(hours=ci + 1),
                    updated_at=post.created_at + timedelta(hours=ci + 1),
                ))

        # Reel likes/comments: also only among seed users.
        for reel in reels:
            possible = [u for u in all_users if u.id != reel.user_id]
            random.shuffle(possible)
            for liker in possible[:random.randint(1, min(6, len(possible)))]:
                db.session.add(Reels_Likes(reel_id=reel.id, user_id=liker.id))
            for ci in range(random.randint(1, 3)):
                commenter = possible[ci % len(possible)]
                db.session.add(Comments(
                    reel_id=reel.id,
                    user_id=commenter.id,
                    content=make_comment_text(REEL_COMMENTS, commenter.id, ci),
                    created_at=reel.created_at + timedelta(hours=ci + 1),
                    updated_at=reel.created_at + timedelta(hours=ci + 1),
                ))

        db.session.commit()

        print("\n=== 5tory seed 완료 ===")
        print(f"새 유저: {len(created_users)}")
        print(f"게시물: {len(posts)}")
        print(f"릴스: {len(reels)}")
        print(f"스토리: {len(stories)}")
        print("비밀번호: 1234")
        if skipped:
            print("이미 존재해서 건너뛴 seed 유저:", ", ".join(skipped))
        print("기존 DB 데이터는 삭제/수정하지 않았습니다.")


if __name__ == "__main__":
    seed()
