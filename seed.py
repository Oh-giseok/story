"""Create or safely rebuild the portfolio seed dataset.

python seed.py --dry-run       Inspect reset targets without changing the DB.
python seed.py --reset-seed   Replace only confidently identified seed rows.
python seed.py                Add missing seed rows; never reset existing rows.
"""
from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
try:
    import imageio_ffmpeg
except ImportError:  # Required only when creating or validating Seed videos.
    imageio_ffmpeg = None
from flask import Flask
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from story import db
from story.models import (
    Comments, Friendship, Notification,
    Post, PostComment, PostLike, PostRepost, Reels, Reels_Likes, Story,
    StoryLikes, User,
)

PASSWORD = "1234"
SEED_NOTIFICATION_MARKER = "__portfolio_seed__:v3:"
LEGACY_SEED_IDENTITIES = (
    ("seed_film_jun", "seed_film_jun@5tory.local", "seed_media/profiles/film_jun.svg"),
    ("seed_plant_nana", "seed_plant_nana@5tory.local", "seed_media/profiles/plant_nana.svg"),
    ("seed_draw_jiu", "seed_draw_jiu@5tory.local", "seed_media/profiles/draw_jiu.svg"),
)
POST_COUNTS = (5, 6, 7, 5, 6, 6, 7, 6, 5, 7)
REEL_COUNTS = (3, 4, 3, 4, 3, 4, 3, 4, 3, 4)
# slug, display name, intro, topic, visual hue, topic-appropriate captions
PEOPLE = [
    ("mori_cafe", "김서윤", "골목 카페와 작은 디저트를 기록해요", "카페", 28,
     ["퇴근길에 발견한 작은 카페. 창가 자리가 좋아 책 한 챕터 읽고 왔어요.", "고소한 플랫화이트와 레몬 케이크. 다음엔 친구랑 와야지.", "비 오는 날엔 조용한 카페에 오래 앉아 있고 싶다.", "동네 골목에서 찾은 라떼 맛집, 오래오래 있었으면.", "햇살 좋은 자리에서 커피 한 잔. 별일 아닌데 기분 좋네.", "원두 향이 좋아서 한 봉지 사 왔어요.", "주말 아침을 천천히 시작하는 방법 ☕", "오늘의 커피는 산미가 조금 있는 쪽.", "다음에는 노트북 들고 와서 오래 있어야지."]),
    ("trip_min", "최민재", "주말마다 낯선 동네를 걷는 여행자", "여행", 195,
     ["기차 창밖으로 바다가 보이기 시작하면 여행이 실감나요.", "계획 없이 골목을 걷다가 마음에 드는 풍경을 만났어요.", "바람 쐬러 다녀온 바닷가. 돌아오는 길까지 좋았다.", "시장 구경하고 따뜻한 국수 한 그릇, 완벽한 여행 코스.", "돌아오는 길에 찍은 하늘이 오늘의 베스트 컷.", "낯선 동네의 아침 산책은 늘 조금 설렌다.", "다음에는 하루 더 머물고 싶은 곳.", "여행지에서 작은 서점을 발견했어요.", "기차역 근처 빵집까지 찾아가길 잘했다."]),
    ("run_haru", "이하루", "퇴근 후 한강을 달리고 기록합니다", "러닝", 105,
     ["아침 공기가 선선해서 평소보다 조금 더 뛰었어요. 6km 완료 🏃", "기록보다 꾸준함에 집중한 오늘의 러닝.", "한강 노을 보면서 천천히 달리니 피로가 풀리네요.", "새 러닝화 첫날, 발이 가벼워 한 바퀴 더 돌았습니다.", "비 오기 전에 짧게 뛰고 들어왔어요.", "오늘은 페이스 신경 쓰지 않고 편하게 5km.", "러닝 끝나고 마시는 물이 제일 맛있다.", "주말 아침 운동으로 하루를 일찍 시작했어요.", "조금 힘들었지만 끝까지 뛰고 나니 뿌듯."]),
    ("fashion_roe", "서로운", "편하게 오래 입을 옷을 기록해요", "패션", 0,
     ["자주 손이 가는 셔츠와 편한 바지. 오늘은 이 조합으로.", "톤을 맞추니 액세서리는 하나만 해도 충분하네요.", "오래 입고 싶은 기본 아이템을 하나 찾았어요.", "걷기 좋은 날이라 가벼운 재킷을 꺼냈습니다.", "오늘의 색은 차분한 네이비.", "빈티지 숍에서 딱 맞는 가방을 발견했어요.", "편한 신발 덕분에 동네를 오래 걸었습니다.", "옷장 정리하다 다시 발견한 좋아하는 니트.", "주말 약속에는 너무 꾸미지 않은 쪽이 좋아요."]),
    ("dev_joon", "박준호", "작은 제품을 만들며 배우는 개발자", "개발", 220,
     ["카페에서 막힌 부분을 정리하다가 실마리를 찾았다. 기록해두기.", "새 기능을 붙이고 나니 이제야 화면이 조금씩 모양을 갖춘다.", "오늘은 테스트를 정리하고 문서를 업데이트했어요.", "작업하다 고개를 들었더니 창밖이 벌써 어두워졌네.", "작은 개선 하나가 전체 흐름을 꽤 편하게 만들었다.", "배운 내용을 잊기 전에 노트에 적어두는 편.", "오랜만에 사이드 프로젝트를 한 걸음 진행했어요.", "집중이 잘되는 날엔 할 일을 조금 더 해둡니다.", "버그를 고쳤으니 이제 커피 마실 시간 ☕"]),
    ("pet_dodo", "오도현", "강아지 도도와 동네를 산책해요", "반려견", 48,
     ["도도랑 공원 한 바퀴. 낙엽 밟는 소리가 신났나 봐요 🐕", "산책 가방만 들어도 현관 앞에서 기다리는 중.", "오늘은 새 장난감보다 택배 상자가 더 좋대요.", "햇볕 드는 자리에서 낮잠 자는 모습이 제일 평화롭다.", "친구 강아지와 처음 만났는데 금방 친해졌어요.", "산책 후 물 한 그릇 비우고 꿀잠.", "도도가 좋아하는 길로 천천히 걸었어요.", "털 정리하고 나니 더 보송보송해졌습니다.", "주말 아침부터 신나게 놀고 쉬는 중."]),
    ("food_tae", "강태윤", "만드는 것도 먹는 것도 좋아합니다", "음식", 18,
     ["퇴근하고 냉장고 재료로 만든 파스타. 생각보다 잘 됐어요.", "주말 브런치로 팬케이크 🥞 천천히 구워 먹었습니다.", "처음 만들어본 바질페스토, 다음엔 양을 더 넉넉히 해야지.", "시장에서 사 온 재료로 따뜻한 국 한 냄비 끓였어요.", "간단하지만 든든한 오늘 점심.", "새로 산 그릇에 담으니 집밥도 조금 특별해 보인다.", "레시피보다 취향대로 넣었는데 꽤 괜찮았어요.", "디저트는 나눠 먹으려고 했는데 결국 하나 더 먹음.", "좋아하는 재료 듬뿍 넣은 샌드위치."]),
    ("music_ian", "한이안", "작은 공연장과 플레이리스트", "음악", 270,
     ["퇴근길 플레이리스트에 새 곡을 추가했어요. 밤 산책이 길어질 듯.", "작은 공연장에서 듣는 라이브는 역시 다르다.", "좋아하는 밴드 앙코르까지 듣고 돌아가는 길.", "주말 오후 레코드샵 구경, 예상보다 오래 머물렀어요.", "요즘 자주 듣는 앨범의 첫 트랙.", "공연장 조명이 켜지는 순간을 오래 기억하고 싶다.", "친구가 알려준 곡이 하루 종일 머릿속에 맴돌아요.", "비 오는 날 듣기 좋은 노래를 모았습니다.", "이어폰 끼고 걷기 딱 좋은 저녁."]),
    ("nature_nana", "정나은", "식물과 산책길에서 계절을 찾아요", "자연", 130,
     ["새 잎이 올라왔다 🌱 매일 조금씩 자라는 게 신기해요.", "분갈이하고 창가 자리도 바꿔줬어요. 잘 적응하길.", "햇빛 좋은 오후, 식물들 물 주는 시간.", "작은 화분 하나가 방 분위기를 바꿔주는 것 같아요.", "잎 끝에 맺힌 물방울이 예뻐서 한 장.", "초보 식집사의 몬스테라 근황.", "주말에 화원 다녀와서 초록 친구가 늘었습니다.", "새순이 나올 때마다 괜히 기분이 좋아져요.", "산책길에서 만난 나무에 가을이 왔네."]),
    ("weekend_su", "이수현", "친구들과 평범한 주말을 모아요", "주말", 345,
     ["오랜만에 다 같이 모인 저녁. 얘기하다 보니 시간이 금방 갔다.", "약속 없이 만났는데 하루가 꽉 찼네.", "친구가 알려준 동네 맛집, 다음엔 다 같이 와야지.", "사진첩 정리하다 지난 주말 장면 발견.", "햇살 좋은 날 공원에서 오래 앉아 있었어요.", "별 계획 없던 토요일이 제일 기억에 남기도 해.", "각자 바빠도 이렇게 가끔 모이면 좋다.", "산책하다 들른 빵집에서 간식도 챙겼어요.", "이번 주말은 천천히, 좋아하는 사람들과."]),
]
STORY_CAPTIONS = ["오늘의 작은 기록", "잠깐 쉬어 가는 중", "이 순간이 좋아서", "지나가기 전에 한 장", "오늘의 짧은 영상"]
REEL_CAPTIONS = ["오늘의 한 장면", "천천히 담아본 하루", "주말 기록", "요즘 좋아하는 순간"]
COMMENT_LINES = [
    "분위기 너무 좋다, 여긴 어디야?", "사진에서 오늘 날씨가 느껴져 ☀️", "이런 기록 덕분에 나도 가보고 싶어졌어.",
    "색감이 참 편안하다. 저장해둘게!", "다음에 같이 가자, 여기 궁금했어.", "천천히 보고 있으니 기분까지 좋아지네.",
    "이 조합은 꼭 따라 해봐야겠다.", "오늘도 좋은 하루 보냈구나 🙂", "마지막 장면까지 다 좋다!", "꾸준히 하는 모습 멋지다.",
    "여기 나도 좋아하는 곳이야. 반갑다!", "다음 기록도 기다릴게 🌿", "딱 주말에 필요한 풍경이다.",
]
FRIEND_PAIRS = [(0,1),(0,4),(0,6),(1,3),(1,7),(2,3),(2,5),(2,8),(3,8),(4,6),(4,9),(5,7),(5,9),(6,7),(8,9)]


def seed_app() -> Flask:
    """Build a DB-only Flask context without starting the web app or Redis."""
    root = Path(__file__).resolve().parent
    app = Flask("seed", static_folder=str(root / "story" / "static"), instance_path=str(root / "instance"))
    app.config.from_object("config")
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"timeout": 30}}
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    return app


def _slug_map():
    return {entry[0]: entry for entry in PEOPLE}


def _profile_path(slug):
    return f"seed_media/profiles/v4/{slug}.jpg"


def _legacy_profile_paths(slug):
    return {f"seed_media/profiles/{slug}.svg", f"seed_media/profiles/v2/{slug}.svg", f"profile/{slug}.svg"}


SHEET_BY_SLUG = {
    "mori_cafe": "cafe", "trip_min": "travel", "run_haru": "running", "fashion_roe": "fashion",
    "dev_joon": "development", "pet_dodo": "pet", "food_tae": "food", "music_ian": "music",
    "nature_nana": "nature", "weekend_su": "weekend",
}


def _write_photo_svg(path: Path, sheet_name: str, tile_index: int, sheet_size: tuple[int, int]):
    """Create a lightweight SVG viewport for one distinct photo in the contact sheet."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = sheet_size
    x0, x1 = round((tile_index % 4) * width / 4) + 4, round((tile_index % 4 + 1) * width / 4) - 4
    y0, y1 = round((tile_index // 4) * height / 5) + 4, round((tile_index // 4 + 1) * height / 5) - 4
    crop_width = min(x1 - x0, int((y1 - y0) * 0.8))
    center = (x0 + x1) // 2
    x0, x1 = center - crop_width // 2, center + (crop_width - crop_width // 2)
    seed_root = next(parent for parent in path.parents if parent.name == "seed_media")
    image_ref = os.path.relpath(seed_root / "photo_sheets" / f"{sheet_name}.jpg", path.parent).replace("\\", "/")
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="1200" viewBox="{x0} {y0} {x1-x0} {y1-y0}"><image href="{image_ref}" width="{width}" height="{height}"/></svg>''', encoding="utf-8")


def _write_photo_jpg(path: Path, sheet: Path, tile_index: int):
    """Write a self-contained web image; SVG external references fail in img contexts."""
    if path.exists():
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"기존 Seed 이미지 파일이 손상되었습니다: {path}")
        return
    image = cv2.imread(str(sheet))
    if image is None:
        raise RuntimeError(f"Seed 사진 시트를 읽을 수 없습니다: {sheet}")
    height, width = image.shape[:2]
    x0, x1 = round((tile_index % 4) * width / 4) + 4, round((tile_index % 4 + 1) * width / 4) - 4
    y0, y1 = round((tile_index // 4) * height / 5) + 4, round((tile_index // 4 + 1) * height / 5) - 4
    photo = cv2.resize(image[y0:y1, x0:x1], (720, 900), interpolation=cv2.INTER_AREA)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), photo, [cv2.IMWRITE_JPEG_QUALITY, 86, cv2.IMWRITE_JPEG_OPTIMIZE, 1]):
        raise RuntimeError(f"Seed JPG 생성 실패: {path}")


def _write_h264(path: Path, sheet: Path, tile_index: int, duration: float):
    """Encode a compact 9:16 H.264/AAC MP4 using the bundled FFmpeg binary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if imageio_ffmpeg is None:
            raise RuntimeError("기존 Seed 영상 검증에는 imageio-ffmpeg가 필요합니다.")
        data = path.read_bytes()
        if b"ftyp" not in data[:16] or b"avc1" not in data or b"mp4a" not in data:
            raise RuntimeError(f"기존 파일을 덮어쓰지 않습니다. Seed 미디어 경로 충돌: {path}")
        _frames, existing_duration = imageio_ffmpeg.count_frames_and_secs(str(path))
        if not 4 <= existing_duration <= 8:
            raise RuntimeError(f"기존 Seed MP4의 길이를 확인할 수 없습니다: {path}")
        return existing_duration
    if imageio_ffmpeg is None:
        raise RuntimeError("새 Seed 영상을 생성하려면 imageio-ffmpeg가 필요합니다.")
    sheet_image = cv2.imread(str(sheet))
    if sheet_image is None:
        raise RuntimeError(f"Seed 사진 시트를 읽을 수 없습니다: {sheet}")
    sheet_h, sheet_w = sheet_image.shape[:2]
    x0, x1 = round((tile_index % 4) * sheet_w / 4) + 4, round((tile_index % 4 + 1) * sheet_w / 4) - 4
    y0, y1 = round((tile_index // 4) * sheet_h / 5) + 4, round((tile_index // 4 + 1) * sheet_h / 5) - 4
    photo = sheet_image[y0:y1, x0:x1]
    width, height, fps = 360, 640, 15
    frames = round(duration * fps)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
               "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "29", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        crop_h = min(photo.shape[0], photo.shape[1] * 16 // 9)
        crop_w = min(photo.shape[1], crop_h * 9 // 16)
        for index in range(frames):
            t = index / max(1, frames - 1)
            zoom = 1.03 + .035 * t
            ch, cw = max(1, int(crop_h / zoom)), max(1, int(crop_w / zoom))
            cx = photo.shape[1] // 2 + int((t - .5) * max(0, photo.shape[1] - cw) * .4)
            cy = photo.shape[0] // 2 + int((.5 - t) * max(0, photo.shape[0] - ch) * .3)
            left, top = max(0, min(photo.shape[1]-cw, cx-cw//2)), max(0, min(photo.shape[0]-ch, cy-ch//2))
            frame = cv2.resize(photo[top:top+ch, left:left+cw], (width, height), interpolation=cv2.INTER_AREA)
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        stderr = process.stderr.read()
        return_code = process.wait()
    except Exception:
        process.kill()
        process.wait()
        path.unlink(missing_ok=True)
        raise
    if return_code or not path.is_file():
        path.unlink(missing_ok=True)
        raise RuntimeError(f"H.264 영상 생성 실패: {path.name}: {stderr.decode('utf-8', errors='replace')}")
    data = path.read_bytes()
    if b"ftyp" not in data[:16] or b"avc1" not in data or b"mp4a" not in data:
        raise RuntimeError(f"H.264/AAC MP4 인코딩을 확인할 수 없습니다: {path}")
    _frames, encoded_duration = imageio_ffmpeg.count_frames_and_secs(str(path))
    if abs(encoded_duration - duration) > 0.15:
        raise RuntimeError(f"영상 길이 확인 실패 ({encoded_duration:.2f}s): {path}")
    return encoded_duration


def _make_thumbnail(video: Path, thumb: Path):
    if thumb.exists():
        return
    thumb.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    capture.set(cv2.CAP_PROP_POS_MSEC, 1800)
    ok, frame = capture.read()
    capture.release()
    if not ok or not cv2.imwrite(str(thumb), frame, [cv2.IMWRITE_JPEG_QUALITY, 86]):
        raise RuntimeError(f"영상 썸네일 생성 실패: {video}")


def build_assets(root: Path):
    """Build only v2 seed assets, separated from ordinary upload directories."""
    static = root / "static"
    reel_root = static / "reels_uploads"
    assets = {"profiles": [], "posts": [], "stories": [], "story_videos": [], "reels": []}
    serial = 0
    now = datetime.utcnow()
    for user_index, person in enumerate(PEOPLE):
        slug, name, _intro, topic, hue, captions = person
        sheet_name = SHEET_BY_SLUG[slug]
        sheet = static / "seed_media" / "photo_sheets" / f"{sheet_name}.jpg"
        if not sheet.is_file():
            raise FileNotFoundError(f"필수 Seed 사진 시트가 없습니다: {sheet}")
        dimensions = cv2.imread(str(sheet))
        if dimensions is None:
            raise RuntimeError(f"Seed 사진 시트를 읽지 못했습니다: {sheet}")
        sheet_size = (dimensions.shape[1], dimensions.shape[0])
        profile = static / _profile_path(slug)
        _write_photo_jpg(profile, sheet, 0)
        assets["profiles"].append((slug, profile, _profile_path(slug)))
        for post_index in range(POST_COUNTS[user_index]):
            count = 2
            image_paths, media_paths = [], []
            for image_index in range(count):
                serial += 1
                suffix = chr(ord('a') + image_index)
                relative = f"seed_media/posts/v4/{slug[:2]}/p{post_index+1:02}{suffix}.jpg"
                path = static / relative
                _write_photo_jpg(path, sheet, 1 + post_index * 2 + image_index)
                image_paths.append(path); media_paths.append(relative)
            assets["posts"].append((slug, post_index, image_paths, media_paths))
        for story_index in range(5):
            if story_index == 4:
                duration = 4.8 + (user_index % 3) * .55
                video = static / f"seed_media/story_videos/v3/{slug}.mp4"
                duration = _write_h264(video, sheet, 19, duration)
                thumb = static / f"seed_media/story_videos/v3/{slug}_thumb.jpg"
                _make_thumbnail(video, thumb)
                assets["story_videos"].append((slug, story_index, video, thumb,
                                               f"seed_media/story_videos/v3/{slug}.mp4",
                                               f"seed_media/story_videos/v3/{slug}_thumb.jpg", duration))
            else:
                relative = f"seed_media/stories/v4/{slug}_{story_index+1}.jpg"
                path = static / relative
                _write_photo_jpg(path, sheet, 15 + story_index)
                assets["stories"].append((slug, story_index, path, relative))
        for reel_index in range(REEL_COUNTS[user_index]):
            duration = 5.2 + ((user_index + reel_index * 2) % 6) * .38
            video = reel_root / "videos" / f"seedv3_{slug}_{reel_index+1:02}.mp4"
            thumb = reel_root / "thumbnails" / f"seedv3_{slug}_{reel_index+1:02}.jpg"
            duration = _write_h264(video, sheet, 1 + (reel_index * 2 + 1) % 14, duration)
            _make_thumbnail(video, thumb)
            assets["reels"].append((slug, reel_index, video, thumb, video.name, thumb.name, duration))

    missing = [str(path) for group in assets.values() for item in group for path in item
               if isinstance(path, Path) and not path.is_file()]
    if missing:
        raise FileNotFoundError("필수 Seed 미디어 누락:\n" + "\n".join(missing))
    return assets


def _media_paths(value):
    return [part.strip().lstrip("/") for part in (value or "").split(",") if part.strip()]


def _is_seed_post(post, owner_slug):
    paths = _media_paths(post.media_url)
    return bool(paths) and all(
        path.startswith(f"seed_media/posts/{owner_slug[:2]}/")
        or path.startswith(f"seed_media/posts/v2/{owner_slug[:2]}/")
        or path.startswith(f"seed_media/posts/v3/{owner_slug[:2]}/")
        or path.startswith(f"seed_media/posts/v4/{owner_slug[:2]}/")
        or (path.startswith("static/seed_media/posts/") and owner_slug in path)
        or (path.startswith("seed_media/posts/") and owner_slug in Path(path).name)
        for path in paths
    )


def _is_seed_reel(reel, owner_slug):
    name = Path((reel.video_url or "").replace("\\", "/")).name
    return bool(re.fullmatch(
        rf"(?:seedv[23]_)?{re.escape(owner_slug)}_(?:reel_)?\d+\.(?:mp4|webm)", name, re.I
    ))


def _is_seed_story(story, owner_slug):
    path = (story.media_url or "").lstrip("/").removeprefix("static/")
    return path.startswith("seed_media/stories/") and owner_slug in Path(path).name or (
        path.startswith("seed_media/story_videos/") and Path(path).stem.startswith(owner_slug)
    )


def _post_order(post, fallback=0):
    for path in _media_paths(post.media_url):
        name = Path(path).name
        match = re.search(r"p(\d{1,2})[a-z]?\.(?:svg|jpe?g)$", name, re.I) or re.search(r"_(\d{1,2})\.(?:svg|jpe?g)$", name, re.I)
        if match:
            return max(0, int(match.group(1)) - 1)
    return fallback


def _reel_order(reel, fallback=0):
    match = re.search(r"_(\d+)\.(?:mp4|webm)$", Path(reel.video_url or "").name, re.I)
    return max(0, int(match.group(1)) - 1) if match else fallback


def _story_order(story, fallback=0):
    name = Path(story.media_url or "").name
    match = re.search(r"_(\d+)\.(?:svg|jpe?g)$", name, re.I)
    if match:
        return max(0, int(match.group(1)) - 1)
    if name.lower().endswith(".mp4"):
        return 4
    return fallback


def plan_reset():
    """Classify only rows with both stable seed identity and seed media markers."""
    users, ambiguous, legacy = [], [], []
    by_slug = _slug_map()
    for slug in by_slug:
        username = f"seed_{slug}"
        user = User.query.filter_by(username=username).first()
        if user is None:
            continue
        expected_email = f"{username}@5tory.local"
        if user.email != expected_email:
            ambiguous.append(f"User {username}: email does not match the Seed identity")
            continue
        users.append((slug, user))
    for username, email, profile_path in LEGACY_SEED_IDENTITIES:
        old_user = User.query.filter_by(username=username).first()
        if old_user is None:
            continue
        if old_user.email == email and old_user.profile_img_url == profile_path:
            legacy.append(old_user)
        else:
            ambiguous.append(f"Legacy account {username}: old Seed signature does not match")
    if ambiguous:
        return {"users": users, "legacy_users": legacy, "posts": [], "reels": [], "stories": [], "friendships": [], "notifications": [], "unsafe": ambiguous, "media": []}

    seed_ids = {user.id for _, user in users}
    if legacy:
        seed_ids.update(user.id for user in legacy)
    seed_posts, seed_reels, seed_stories, unsafe = [], [], [], []
    for slug, user in users:
        all_posts = Post.query.filter_by(user_id=user.id).all()
        user_posts = [post for post in all_posts if _is_seed_post(post, slug)]
        if len(all_posts) != len(user_posts):
            unsafe.append(f"{user.username}: {len(all_posts)-len(user_posts)} Post(s) without a seed media marker")
        seed_posts.extend(user_posts)
        all_reels = Reels.query.filter_by(user_id=user.id).all()
        user_reels = [reel for reel in all_reels if _is_seed_reel(reel, slug)]
        if len(all_reels) != len(user_reels):
            unsafe.append(f"{user.username}: {len(all_reels)-len(user_reels)} Reel(s) without a seed filename marker")
        seed_reels.extend(user_reels)
        all_stories = Story.query.filter_by(user_id=user.id).all()
        user_stories = [story for story in all_stories if _is_seed_story(story, slug)]
        if len(all_stories) != len(user_stories):
            unsafe.append(f"{user.username}: {len(all_stories)-len(user_stories)} Story(ies) without a seed media marker")
        seed_stories.extend(user_stories)

    # Preserve accounts, friendships, friendship notifications and chats. Reset
    # only Seed-marked media rows and their seed-to-seed reactions.
    post_ids = [row.id for row in seed_posts]
    reel_ids = [row.id for row in seed_reels]
    story_ids = [row.id for row in seed_stories]
    if seed_ids:
        # A seed-owned item with reactions/comments from non-seed users is preserved, not cascaded away.
        for model, fk, ids, label in (
            (PostLike, PostLike.post_id, post_ids, "PostLike"),
            (PostComment, PostComment.post_id, post_ids, "PostComment"),
            (PostRepost, PostRepost.post_id, post_ids, "PostRepost"),
            (Reels_Likes, Reels_Likes.reel_id, reel_ids, "Reels_Likes"),
            (Comments, Comments.reel_id, reel_ids, "Reel Comment"),
            (StoryLikes, StoryLikes.story_id, story_ids, "StoryLike"),
        ):
            if ids and model.query.filter(fk.in_(ids), ~model.user_id.in_(seed_ids)).count():
                unsafe.append(f"Seed media has {label} activity from a non-seed account")
        if post_ids and Notification.query.filter(
            Notification.post_id.in_(post_ids),
            (~Notification.actor_id.in_(seed_ids) | ~Notification.recipient_id.in_(seed_ids)),
        ).count():
            unsafe.append("Seed Post has a Notification involving a non-seed account")

    for old_user in legacy:
        unsafe.append(
            f"Legacy Seed account {old_user.username} is outside the current dataset manifest; "
            "its account, media and relationships are preserved pending review"
        )
        if friendship_ids := [row.id for row in Friendship.query.filter(
            Friendship.user_low_id.in_(seed_ids), Friendship.user_high_id.in_(seed_ids)
        ).all()]:
            if Notification.query.filter(
                Notification.friendship_id.in_(friendship_ids),
                (~Notification.actor_id.in_(seed_ids) | ~Notification.recipient_id.in_(seed_ids)),
            ).count():
                unsafe.append("Seed Friendship has a Notification involving a non-seed account")

    marker_notifications = Notification.query.filter(
        Notification.actor_id.in_(seed_ids or [-1]), Notification.recipient_id.in_(seed_ids or [-1]),
        Notification.message.like(f"{SEED_NOTIFICATION_MARKER}%")
    ).all()
    notification_candidates = [row for row in marker_notifications if not row.is_read]
    friendship_candidates = []
    for notice in notification_candidates:
        if notice.message == f"{SEED_NOTIFICATION_MARKER}friendship" and notice.friendship_id:
            edge = db.session.get(Friendship, notice.friendship_id)
            if edge and edge.created_at == edge.updated_at and Notification.query.filter(
                Notification.friendship_id == edge.id, Notification.id != notice.id
            ).count() == 0:
                friendship_candidates.append(edge)
    media = _collect_seed_media(users + [(next(slug for old_name, _email, _profile in LEGACY_SEED_IDENTITIES if old_name == user.username), user) for user in legacy], seed_posts, seed_reels, seed_stories)
    return {"users": users, "posts": seed_posts, "reels": seed_reels, "stories": seed_stories,
            "legacy_users": legacy,
            "friendships": friendship_candidates, "notifications": notification_candidates,
            "unsafe": unsafe, "media": media}


def _collect_seed_media(users, posts, reels, stories):
    root = Path(__file__).resolve().parent / "story" / "static"
    files = set()
    for _slug, user in users:
        if user.profile_img_url:
            files.add(root / user.profile_img_url)
    for post in posts:
        for ref in _media_paths(post.media_url) + _media_paths(post.thumbnail_url):
            if ref.startswith(("seed_media/", "static/seed_media/")):
                files.add(root / ref.removeprefix("static/"))
    for story in stories:
        for ref in (story.media_url, story.thumbnail_url):
            if ref and ref.startswith("seed_media/"):
                files.add(root / ref)
    for reel in reels:
        video = Path((reel.video_url or "").replace("\\", "/")).name
        thumb = Path((reel.thumbnail_url or "").replace("\\", "/")).name
        slug = next((s for s, _u in users if s in video), None)
        if slug and re.fullmatch(rf"(?:seedv[23]_)?{re.escape(slug)}_(?:reel_)?\d+\.(?:mp4|webm)", video, re.I):
            files.add(root / "reels_uploads" / "videos" / video)
        if slug and re.fullmatch(rf"(?:seedv[23]_)?{re.escape(slug)}_(?:reel_)?\d+\.jpg", thumb, re.I):
            files.add(root / "reels_uploads" / "thumbnails" / thumb)
    return sorted(path for path in files if path.is_file())


def _referenced_media_paths(static_root: Path):
    """Collect remaining static references once before cleaning captured files."""
    references = set()

    def add(value):
        if not value:
            return
        normalized = value.replace("\\", "/").lstrip("/").removeprefix("static/")
        try:
            target = (static_root / normalized).resolve()
            target.relative_to(static_root)
            references.add(target)
        except (OSError, RuntimeError, ValueError):
            return

    for user in User.query.all():
        add(user.profile_img_url)
    for post in Post.query.all():
        for value in _media_paths(post.media_url) + _media_paths(post.thumbnail_url):
            add(value)
    for story in Story.query.all():
        add(story.media_url); add(story.thumbnail_url)
    for reel in Reels.query.all():
        video = Path((reel.video_url or "").replace("\\", "/")).name
        thumb = Path((reel.thumbnail_url or "").replace("\\", "/")).name
        if video:
            add(f"reels_uploads/videos/{video}")
        if thumb:
            add(f"reels_uploads/thumbnails/{thumb}")
    return references


def _counts_for_plan(plan):
    seed_ids = [user.id for _, user in plan["users"]]
    post_ids = [item.id for item in plan["posts"]]
    reel_ids = [item.id for item in plan["reels"]]
    story_ids = [item.id for item in plan["stories"]]
    return {
        "Seed Users (retained)": len(seed_ids), "Legacy Seed Users (preserved)": len(plan.get("legacy_users", [])), "Posts": len(post_ids), "Post Likes": PostLike.query.filter(PostLike.post_id.in_(post_ids)).count() if post_ids else 0,
        "Post Comments": PostComment.query.filter(PostComment.post_id.in_(post_ids)).count() if post_ids else 0,
        "Post Reposts": PostRepost.query.filter(PostRepost.post_id.in_(post_ids)).count() if post_ids else 0,
        "Reels": len(reel_ids), "Reel Likes": Reels_Likes.query.filter(Reels_Likes.reel_id.in_(reel_ids)).count() if reel_ids else 0,
        "Reel Comments": Comments.query.filter(Comments.reel_id.in_(reel_ids)).count() if reel_ids else 0,
        "Stories": len(story_ids), "Story Likes": StoryLikes.query.filter(StoryLikes.story_id.in_(story_ids)).count() if story_ids else 0,
        "Friendships": len(plan["friendships"]),
        "Notifications": len(plan["notifications"]),
    }


def _reset_seed_rows(plan):
    seed_ids = [user.id for _, user in plan["users"]]
    post_ids = [item.id for item in plan["posts"]]
    reel_ids = [item.id for item in plan["reels"]]
    story_ids = [item.id for item in plan["stories"]]
    friendship_ids = [item.id for item in plan["friendships"]]
    notification_ids = [item.id for item in plan["notifications"]]
    # Keep all account and friendship records so user-owned activity remains intact.
    if post_ids:
        Notification.query.filter(Notification.post_id.in_(post_ids), Notification.actor_id.in_(seed_ids),
                                  Notification.recipient_id.in_(seed_ids)).delete(synchronize_session=False)
        PostLike.query.filter(PostLike.post_id.in_(post_ids), PostLike.user_id.in_(seed_ids)).delete(synchronize_session=False)
        PostComment.query.filter(PostComment.post_id.in_(post_ids), PostComment.user_id.in_(seed_ids)).delete(synchronize_session=False)
        PostRepost.query.filter(PostRepost.post_id.in_(post_ids), PostRepost.user_id.in_(seed_ids)).delete(synchronize_session=False)
        Post.query.filter(Post.id.in_(post_ids)).delete(synchronize_session=False)
    if reel_ids:
        Reels_Likes.query.filter(Reels_Likes.reel_id.in_(reel_ids), Reels_Likes.user_id.in_(seed_ids)).delete(synchronize_session=False)
        Comments.query.filter(Comments.reel_id.in_(reel_ids), Comments.user_id.in_(seed_ids)).delete(synchronize_session=False)
        Reels.query.filter(Reels.id.in_(reel_ids)).delete(synchronize_session=False)
    if story_ids:
        StoryLikes.query.filter(StoryLikes.story_id.in_(story_ids), StoryLikes.user_id.in_(seed_ids)).delete(synchronize_session=False)
        Story.query.filter(Story.id.in_(story_ids)).delete(synchronize_session=False)
    if notification_ids:
        Notification.query.filter(Notification.id.in_(notification_ids), Notification.is_read.is_(False)).delete(synchronize_session=False)
    if friendship_ids:
        Friendship.query.filter(Friendship.id.in_(friendship_ids)).delete(synchronize_session=False)


def migrate_seed_media_v4():
    """Replace legacy linked-SVG seed media with raster images and remove old seed rows.

    Non-seed reactions are preserved by retaining the affected Post row and changing
    only its media reference. Seed accounts and their friendship graph are untouched.
    """
    active = {f"seed_{slug}": slug for slug in _slug_map()}
    users = User.query.filter(User.username.like("seed_%")).all()
    seed_ids = {user.id for user in users}
    external_ids = [user.id for user in User.query.filter(~User.username.like("seed_%")).all()]
    for user in users:
        if user.username in active:
            user.profile_img_url = _profile_path(active[user.username])

    keep_posts = []
    remove_posts = []
    for post in Post.query.filter(Post.user_id.in_(seed_ids or [-1])).all():
        username = next((u.username for u in users if u.id == post.user_id), "")
        slug = active.get(username)
        paths = _media_paths(post.media_url)
        if any("/v4/" in f"/{path}" for path in paths):
            continue
        if any("/v3/" in f"/{path}" for path in paths):
            post.media_url = ",".join(path.replace("/v3/", "/v4/").rsplit(".svg", 1)[0] + ".jpg" for path in paths)
            if post.thumbnail_url:
                post.thumbnail_url = post.thumbnail_url.replace("/v3/", "/v4/").rsplit(".svg", 1)[0] + ".jpg"
            continue

        post_id = post.id
        has_external_activity = any((
            PostLike.query.filter_by(post_id=post_id).filter(PostLike.user_id.in_(external_ids or [-1])).first(),
            PostComment.query.filter_by(post_id=post_id).filter(PostComment.user_id.in_(external_ids or [-1])).first(),
            PostRepost.query.filter_by(post_id=post_id).filter(PostRepost.user_id.in_(external_ids or [-1])).first(),
            Notification.query.filter_by(post_id=post_id).filter(
                (Notification.actor_id.in_(external_ids or [-1])) | (Notification.recipient_id.in_(external_ids or [-1]))
            ).first(),
        ))
        if has_external_activity and slug:
            match = re.search(r"_(\d+)\.(?:svg|jpe?g)$", Path(paths[0]).name, re.I)
            index = max(1, int(match.group(1))) if match else 1
            image = f"seed_media/posts/v4/{slug[:2]}/p{index:02}a.jpg"
            post.media_url = image
            post.thumbnail_url = image
            keep_posts.append(post_id)
        else:
            remove_posts.append(post_id)

    if remove_posts:
        Notification.query.filter(Notification.post_id.in_(remove_posts)).delete(synchronize_session=False)
        PostLike.query.filter(PostLike.post_id.in_(remove_posts)).delete(synchronize_session=False)
        PostComment.query.filter(PostComment.post_id.in_(remove_posts)).delete(synchronize_session=False)
        PostRepost.query.filter(PostRepost.post_id.in_(remove_posts)).delete(synchronize_session=False)
        Post.query.filter(Post.id.in_(remove_posts)).delete(synchronize_session=False)

    # Preserve the second-generation Seed reels, discard first-run Seed reels.
    remove_reels = []
    for reel in Reels.query.filter(Reels.user_id.in_(seed_ids or [-1])).all():
        name = Path((reel.video_url or "").replace("\\", "/")).name
        if name.startswith(("seedv2_", "seedv3_")):
            continue
        if any((
            Reels_Likes.query.filter_by(reel_id=reel.id).filter(Reels_Likes.user_id.in_(external_ids or [-1])).first(),
            Comments.query.filter_by(reel_id=reel.id).filter(Comments.user_id.in_(external_ids or [-1])).first(),
        )):
            continue
        remove_reels.append(reel.id)
    if remove_reels:
        Reels_Likes.query.filter(Reels_Likes.reel_id.in_(remove_reels)).delete(synchronize_session=False)
        Comments.query.filter(Comments.reel_id.in_(remove_reels)).delete(synchronize_session=False)
        Reels.query.filter(Reels.id.in_(remove_reels)).delete(synchronize_session=False)

    # Existing Story rows are Seed-only for these accounts; keep any with external likes.
    remove_stories = []
    for story in Story.query.filter(Story.user_id.in_(seed_ids or [-1])).all():
        media = (story.media_url or "").replace("\\", "/")
        if "/v4/" in media:
            continue
        if "/v3/" in media:
            if media.lower().endswith(".svg"):
                story.media_url = media.replace("/v3/", "/v4/").rsplit(".svg", 1)[0] + ".jpg"
                story.thumbnail_url = story.media_url
            continue
        if StoryLikes.query.filter_by(story_id=story.id).filter(StoryLikes.user_id.in_(external_ids or [-1])).first():
            continue
        remove_stories.append(story.id)
    if remove_stories:
        StoryLikes.query.filter(StoryLikes.story_id.in_(remove_stories)).delete(synchronize_session=False)
        Story.query.filter(Story.id.in_(remove_stories)).delete(synchronize_session=False)

    removed_legacy_accounts = 0
    for username, email, profile_path in LEGACY_SEED_IDENTITIES:
        legacy = User.query.filter_by(username=username, email=email, profile_img_url=profile_path).first()
        if legacy is None:
            continue
        legacy_ids = [legacy.id]
        notices = Notification.query.filter(or_(
            Notification.actor_id.in_(legacy_ids), Notification.recipient_id.in_(legacy_ids)
        )).all()
        # Do not remove a legacy identity if a real account has interacted with it.
        if any((notice.actor_id not in seed_ids or notice.recipient_id not in seed_ids) for notice in notices):
            continue
        edge_ids = [edge.id for edge in Friendship.query.filter(or_(
            Friendship.user_low_id.in_(legacy_ids), Friendship.user_high_id.in_(legacy_ids)
        )).all()]
        if edge_ids:
            Notification.query.filter(Notification.friendship_id.in_(edge_ids)).delete(synchronize_session=False)
        if notices:
            Notification.query.filter(Notification.id.in_([notice.id for notice in notices])).delete(synchronize_session=False)
        if edge_ids:
            Friendship.query.filter(Friendship.id.in_(edge_ids)).delete(synchronize_session=False)
        for model in (PostLike, PostComment, PostRepost, Reels_Likes, Comments, StoryLikes):
            model.query.filter(model.user_id.in_(legacy_ids)).delete(synchronize_session=False)
        # Only remove accounts emptied of authored content by the legacy cleanup.
        has_content = any((
            Post.query.filter_by(user_id=legacy.id).first(),
            Reels.query.filter_by(user_id=legacy.id).first(),
            Story.query.filter_by(user_id=legacy.id).first(),
        ))
        if has_content:
            continue
        db.session.delete(legacy)
        removed_legacy_accounts += 1

    db.session.commit()
    return {"preserved_posts_with_external_activity": len(keep_posts),
            "removed_legacy_posts": len(remove_posts), "removed_legacy_reels": len(remove_reels),
            "removed_legacy_stories": len(remove_stories),
            "removed_legacy_seed_accounts": removed_legacy_accounts}


def _add_if_missing(query, model, values):
    if query.first():
        return False
    db.session.add(model(**values))
    return True


def _create_seed_rows(assets):
    now = datetime.utcnow()
    counts = {key: 0 for key in ("Users", "Posts", "Post Images", "Post Likes", "Post Comments", "Post Reposts",
                                  "Reels", "Reel Likes", "Reel Comments", "Stories", "Story Images", "Story Videos",
                                  "Story Likes", "Friendships", "Notifications")}
    users = {}
    for index, (slug, name, intro, topic, _hue, _captions) in enumerate(PEOPLE):
        username, email = f"seed_{slug}", f"seed_{slug}@5tory.local"
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email, password_hash=generate_password_hash(PASSWORD),
                        name=name, intro=f"{intro} · 관심사: {topic}", profile_img_url=_profile_path(slug),
                        birth=date(1990 + index % 10, 1 + index % 12, 4 + index % 22), status="active",
                        created_at=now - timedelta(days=220 + index * 5), updated_at=now - timedelta(days=220 + index * 5))
            db.session.add(user); db.session.flush(); counts["Users"] += 1
        else:
            # Existing account fields and profile are user-owned; never overwrite them.
            if user.email != email:
                raise RuntimeError(f"기존 계정 이메일이 Seed 식별자와 달라 변경 없이 중단합니다: {username}")
        users[slug] = user

    post_rows, reel_rows, story_rows = [], [], []
    post_assets = {slug: [] for slug, *_ in PEOPLE}
    reel_assets = {slug: [] for slug, *_ in PEOPLE}
    story_assets = {slug: [] for slug, *_ in PEOPLE}
    for asset in assets["posts"]:
        post_assets[asset[0]].append(asset)
    for asset in assets["reels"]:
        reel_assets[asset[0]].append(asset)
    for asset in assets["stories"]:
        story_assets[asset[0]].append((*asset, False))
    for slug, index, video, thumb, relative, thumb_relative, duration in assets["story_videos"]:
        story_assets[slug].append((slug, index, video, relative, True))

    for user_index, person in enumerate(PEOPLE):
        slug = person[0]
        user = users[slug]
        existing_posts = [row for row in Post.query.filter_by(user_id=user.id).all() if _is_seed_post(row, slug)]
        existing_posts.sort(key=lambda row: (row.created_at, row.id))
        post_rows.extend((row, slug, _post_order(row, index)) for index, row in enumerate(existing_posts))
        post_count = len(existing_posts)
        existing_post_media = {row.media_url for row in existing_posts}
        for _slug, post_index, _paths, media_paths in post_assets[slug]:
            if post_count >= POST_COUNTS[user_index]:
                break
            media_value = ",".join(media_paths)
            if media_value in existing_post_media:
                continue
            caption = person[5][post_index % len(person[5])]
            age_days = [91, 75, 62, 48, 39, 27, 18, 10, 4, 1][(post_index * 3 + user.id) % 10]
            created = now - timedelta(days=age_days, hours=(post_index * 5 + user.id) % 21)
            post = Post(user_id=user.id, caption=caption, media_url=media_value, thumbnail_url=media_paths[0],
                        created_at=created, updated_at=created)
            db.session.add(post); db.session.flush()
            post_rows.append((post, slug, post_index)); existing_post_media.add(media_value); post_count += 1
            counts["Posts"] += 1; counts["Post Images"] += len(media_paths)

        existing_reels = [row for row in Reels.query.filter_by(user_id=user.id).all() if _is_seed_reel(row, slug)]
        existing_reels.sort(key=lambda row: (row.created_at, row.id))
        reel_rows.extend((row, slug, _reel_order(row, index)) for index, row in enumerate(existing_reels))
        reel_count = len(existing_reels)
        existing_reel_names = {Path(row.video_url).name for row in existing_reels}
        for _slug, reel_index, _video, _thumb, video_name, thumb_name, duration in reel_assets[slug]:
            if reel_count >= REEL_COUNTS[user_index]:
                break
            if video_name in existing_reel_names:
                continue
            created = now - timedelta(days=[73, 42, 21, 8][reel_index % 4], hours=(reel_index * 7 + user.id) % 18)
            reel = Reels(user_id=user.id, video_url=video_name, thumbnail_url=thumb_name,
                         caption=f"{person[3]} · {REEL_CAPTIONS[reel_index % len(REEL_CAPTIONS)]}",
                         duration=duration, created_at=created, updated_at=created)
            db.session.add(reel); db.session.flush()
            reel_rows.append((reel, slug, reel_index)); existing_reel_names.add(video_name); reel_count += 1
            counts["Reels"] += 1

        existing_stories = [row for row in Story.query.filter_by(user_id=user.id).all() if _is_seed_story(row, slug)]
        existing_stories.sort(key=lambda row: (row.create_date, row.id))
        story_rows.extend((row, slug, _story_order(row, index)) for index, row in enumerate(existing_stories))
        story_count = len(existing_stories)
        existing_story_media = {row.media_url for row in existing_stories}
        for _slug, story_index, _path_or_video, relative, is_video in story_assets[slug]:
            if story_count >= 5:
                break
            media = relative
            if media in existing_story_media:
                continue
            created = now - timedelta(hours=(story_index * 2 + user.id) % 20)
            thumb = f"seed_media/story_videos/v3/{slug}_thumb.jpg" if is_video else media
            story = Story(user_id=user.id, media_url=media, thumbnail_url=thumb,
                          caption=STORY_CAPTIONS[story_index], create_date=created,
                          expires_at=now + timedelta(hours=24 - story_index % 8))
            db.session.add(story); db.session.flush()
            story_rows.append((story, slug, story_index)); existing_story_media.add(media); story_count += 1
            counts["Stories"] += 1
            counts["Story Videos" if is_video else "Story Images"] += 1

    all_users = [users[person[0]] for person in PEOPLE]
    for post, _slug, post_index in post_rows:
        others = [u for u in all_users if u.id != post.user_id]
        random.Random(20261008 + post.id).shuffle(others)
        for user in others[:2 + ((post_index + post.id) % 5)]:
            if _add_if_missing(PostLike.query.filter_by(post_id=post.id, user_id=user.id), PostLike,
                               {"post_id": post.id, "user_id": user.id, "created_at": post.created_at + timedelta(hours=2)}):
                counts["Post Likes"] += 1
        for n, user in enumerate(others[:1 + ((post_index + post.id) % 3)]):
            content = f"{COMMENT_LINES[(post_index * 3 + n + post.id) % len(COMMENT_LINES)]}"
            if not PostComment.query.filter_by(post_id=post.id, user_id=user.id, content=content).first():
                db.session.add(PostComment(post_id=post.id, user_id=user.id, content=content,
                                           created_at=post.created_at + timedelta(hours=3+n)))
                counts["Post Comments"] += 1
        if (post_index + post.id) % 5 == 0:
            sharer = others[-1]
            if _add_if_missing(PostRepost.query.filter_by(post_id=post.id, user_id=sharer.id), PostRepost,
                               {"post_id": post.id, "user_id": sharer.id, "created_at": post.created_at + timedelta(days=1)}):
                counts["Post Reposts"] += 1

    for reel, _slug, reel_index in reel_rows:
        others = [u for u in all_users if u.id != reel.user_id]
        random.Random(20361008 + reel.id).shuffle(others)
        for user in others[:2 + ((reel_index + reel.id) % 5)]:
            if _add_if_missing(Reels_Likes.query.filter_by(reel_id=reel.id, user_id=user.id), Reels_Likes,
                               {"reel_id": reel.id, "user_id": user.id}):
                counts["Reel Likes"] += 1
        for n, user in enumerate(others[:1 + ((reel_index + reel.id) % 2)]):
            content = COMMENT_LINES[(reel_index + n + reel.id + 4) % len(COMMENT_LINES)]
            if not Comments.query.filter_by(reel_id=reel.id, user_id=user.id, content=content).first():
                db.session.add(Comments(reel_id=reel.id, user_id=user.id, content=content,
                                        created_at=reel.created_at + timedelta(hours=4+n)))
                counts["Reel Comments"] += 1

    for story, _slug, story_index in story_rows:
        others = [u for u in all_users if u.id != story.user_id]
        start = (story_index + story.id) % len(others)
        others = others[start:] + others[:start]
        for user in others[:1 + (story.id % 4)]:
            if not StoryLikes.query.filter_by(story_id=story.id, user_id=user.id).first():
                db.session.add(StoryLikes(story_id=story.id, user_id=user.id)); counts["Story Likes"] += 1

    for edge_index, (a, b) in enumerate(FRIEND_PAIRS):
        first, second = users[PEOPLE[a][0]], users[PEOPLE[b][0]]
        low, high = sorted((first.id, second.id))
        friendship = Friendship.query.filter_by(user_low_id=low, user_high_id=high).first()
        friendship_created = friendship is None
        if friendship is None:
            created = now - timedelta(days=70 - edge_index * 3)
            requester = first.id if edge_index % 2 == 0 else second.id
            friendship = Friendship(user_low_id=low, user_high_id=high, requested_by_id=requester,
                                    status="pending" if edge_index in (3,9,13) else "accepted",
                                    created_at=created, updated_at=created)
            db.session.add(friendship); db.session.flush(); counts["Friendships"] += 1
        recipient_id = high if friendship.requested_by_id == low else low
        if not Notification.query.filter_by(friendship_id=friendship.id, recipient_id=recipient_id,
                                            type="friend_request").first():
            marker = (SEED_NOTIFICATION_MARKER + "friendship" if friendship_created
                      else SEED_NOTIFICATION_MARKER + "notification")
            db.session.add(Notification(recipient_id=recipient_id, actor_id=friendship.requested_by_id,
                                        friendship_id=friendship.id, type="friend_request",
                                        message=marker, is_read=False, created_at=friendship.created_at))
            counts["Notifications"] += 1
    return counts


def _validate_seed():
    users = [User.query.filter_by(username=f"seed_{person[0]}").first() for person in PEOPLE]
    if any(user is None for user in users):
        raise RuntimeError("Seed user 검증 실패: 10개 계정이 모두 필요합니다.")
    for user, person in zip(users, PEOPLE):
        slug = person[0]
        posts = Post.query.filter_by(user_id=user.id).all()
        seed_posts = [post for post in posts if _is_seed_post(post, slug)]
        v4_posts = [post for post in seed_posts if any(path.startswith("seed_media/posts/v4/") for path in _media_paths(post.media_url))]
        if not 5 <= len(seed_posts) <= 10 or any(not 1 <= len(_media_paths(post.media_url)) <= 3 for post in v4_posts):
            raise RuntimeError(f"Post 또는 다중 이미지 검증 실패: {user.username}")
        reels = [r for r in Reels.query.filter_by(user_id=user.id).all() if _is_seed_reel(r, slug)]
        if not 3 <= len(reels) <= 4:
            raise RuntimeError(f"Reels 개수 검증 실패: {user.username}")
        for reel in reels:
            video = Path(__file__).resolve().parent / "story" / "static" / "reels_uploads" / "videos" / Path(reel.video_url).name
            thumb = Path(__file__).resolve().parent / "story" / "static" / "reels_uploads" / "thumbnails" / reel.thumbnail_url
            if not video.is_file() or not thumb.is_file() or not 5 <= reel.duration <= 8:
                raise RuntimeError(f"Reel 미디어 검증 실패: {reel.video_url}")
            with video.open("rb") as stream:
                signature = stream.read(2 * 1024 * 1024)
                if Path(reel.video_url).name.startswith("seedv3_") and (
                    b"ftyp" not in signature[:16] or b"avc1" not in signature or b"mp4a" not in signature
                ):
                    raise RuntimeError(f"H.264/AAC MP4 미디어 검증 실패: {video}")
            if Path(reel.video_url).name.startswith("seedv3_"):
                if imageio_ffmpeg is None:
                    raise RuntimeError("Seed 영상 검증에는 imageio-ffmpeg가 필요합니다.")
                _frames, actual_duration = imageio_ffmpeg.count_frames_and_secs(str(video))
                if not 5 <= actual_duration <= 8:
                    raise RuntimeError(f"Reel 영상 길이 검증 실패: {video} ({actual_duration:.2f}s)")
        stories = [s for s in Story.query.filter_by(user_id=user.id).all() if _is_seed_story(s, slug)]
        if len(stories) != 5:
            raise RuntimeError(f"Story 개수/만료 검증 실패: {user.username}")
        v4_stories = [s for s in stories if "/v4/" in s.media_url or "/v3/" in s.media_url]
        if any(s.expires_at <= datetime.utcnow() for s in v4_stories):
            raise RuntimeError(f"새 Seed Story 만료 검증 실패: {user.username}")
        for story in v4_stories:
            story_path = Path(__file__).resolve().parent / "story" / "static" / story.media_url
            if not story_path.is_file():
                raise RuntimeError(f"Story 미디어 누락: {story_path}")
        if len(v4_stories) == 5:
            video_stories = [s for s in v4_stories if s.media_url.endswith(".mp4")]
            if len(video_stories) != 1:
                raise RuntimeError(f"Story 영상 1개 검증 실패: {user.username}")
            story_video = Path(__file__).resolve().parent / "story" / "static" / video_stories[0].media_url
            with story_video.open("rb") as stream:
                signature = stream.read(2 * 1024 * 1024)
                if b"ftyp" not in signature[:16] or b"avc1" not in signature or b"mp4a" not in signature:
                    raise RuntimeError(f"Story H.264/AAC MP4 검증 실패: {story_video}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SNS demo seed data")
    parser.add_argument("--dry-run", action="store_true", help="Reset 대상과 미디어를 출력하고 DB 변경을 하지 않음")
    parser.add_argument("--reset-seed", action="store_true", help="확인 가능한 Seed 데이터만 삭제 후 새 데이터 생성")
    parser.add_argument("--migrate-seed-media-v4", action="store_true",
                        help="Legacy Seed 데이터를 정리하고 게시물 이미지를 실제 JPG 파일로 마이그레이션")
    args = parser.parse_args(argv)
    app = seed_app()
    with app.app_context():
        try:
            if args.migrate_seed_media_v4:
                result = migrate_seed_media_v4()
                print("Seed 미디어 v4 마이그레이션 완료:")
                for key, value in result.items():
                    print(f"{key}: {value}")
                return 0
            if not args.dry_run and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
                # A new teammate's local SQLite DB has no schema yet. create_all
                # is additive and lets the documented one-command seed setup work.
                db.create_all()
            plan = plan_reset()
            counts = _counts_for_plan(plan)
            print("[Seed Dry Run: identified rows]" if args.dry_run else "[Seed plan: identified rows]")
            for key, value in counts.items():
                print(f"{key}: {value}")
            if plan["unsafe"]:
                print("안전하게 판별할 수 없어 삭제하지 않을 데이터:")
                for issue in plan["unsafe"]:
                    print(f"- {issue}")
            if args.dry_run or args.reset_seed:
                print("Seed media 삭제 후보:")
                for path in plan["media"]:
                    print(f"- {path}")
            else:
                print("기본 실행은 기존 Seed 데이터와 미디어를 삭제하지 않습니다.")
            print("일반 사용자 데이터: 삭제하지 않음")
            if args.dry_run:
                db.session.rollback()
                print("Dry Run 완료: 데이터베이스와 미디어를 변경하지 않았습니다.")
                return 0
            if args.reset_seed and plan["unsafe"]:
                raise RuntimeError("모호한 데이터가 있어 Reset을 중단했습니다. 위 항목을 확인하세요.")

            print("[1/5] Seed media 준비 및 검증")
            assets = build_assets(Path(app.static_folder).parent)
            db.session.rollback()
            print("[2/5] Seed 레코드 정리" if args.reset_seed else "[2/5] 누락 Seed 레코드 추가")
            with db.session.begin():
                if args.reset_seed:
                    _reset_seed_rows(plan)
                    db.session.expunge_all()
                added = _create_seed_rows(assets)
                print("[3/5] 관계 및 외래 키 검증")
                _validate_seed()
            # Do not recursively delete directories. Remove only captured files that no row references.
            if args.reset_seed:
                static_root = Path(app.static_folder).resolve()
                referenced = _referenced_media_paths(static_root)
                removed_media = 0
                preserved_media = 0
                for path in plan["media"]:
                    try:
                        path.resolve().relative_to(static_root)
                    except ValueError:
                        print(f"[WARN] static 경로 밖의 파일은 보존합니다: {path}")
                        continue
                    if path.resolve() in referenced:
                        preserved_media += 1
                        continue
                    try:
                        if path.exists():
                            path.unlink()
                            removed_media += 1
                    except OSError as exc:
                        print(f"[WARN] Seed media 정리 건너뜀: {path}: {exc}")
                print(f"Seed media 정리: {removed_media}개 제거, {preserved_media}개 참조로 보존")
            print("[4/5] Database transaction committed")
            print("[5/5] Seed complete")
            for key, value in added.items():
                print(f"{key}: {value}")
            print("Accounts: " + ", ".join(f"seed_{person[0]}" for person in PEOPLE))
            print("Password: 1234")
            return 0
        except Exception as exc:
            db.session.rollback()
            print(f"[ERROR] Seed transaction rolled back: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
