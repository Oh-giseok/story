# Portfolio Seed Data

`seed.py` adds a presentation dataset for the SNS application: ten demo accounts, photo posts, short H.264 reels, active stories, reactions, comments, reposts, friendships, and friend-request notifications. It does not create conversations or messages.

## Commands

Run these from the repository root after installing `requirements.txt`:

```powershell
python seed.py --dry-run
python seed.py --migrate-seed-media-v4
python seed.py
python seed.py --reset-seed
```

- `--dry-run` prints the currently identified Seed rows and media candidates. It does not create tables, run schema migrations, write media, or modify the database.
- The default command is additive. It inserts missing records and leaves existing rows intact.
- `--migrate-seed-media-v4` removes first-run Seed posts/reels/stories and obsolete legacy accounts, migrates the active Seed profiles/posts/stories to real JPG assets, and retains posts with ordinary-user activity by updating only their media path. Take a database backup before running it. Run `python seed.py` after migration to refill missing Seed rows.
- `--reset-seed` replaces only content rows whose media paths/filenames match the Seed markers. It stops before deleting anything if it finds ambiguous account identity, unmarked content owned by a Seed account, or external reactions on Seed media.

Reset deletes database rows in one transaction. Existing Seed account rows, profile choices, ordinary activity, conversations/messages, and unmarked friendships/notifications are preserved. Friendship rows and notifications created by this version carry a private marker in the unused notification message field; unread, unchanged, marked Seed relationships can be rebuilt. It removes captured media files only after commit and only when no remaining profile, post, story, or reel references those paths. Shared photo sheets and unrelated upload directories are left in place. A database failure rolls back the row changes.

Three accounts from the previous portfolio dataset (`seed_film_jun`, `seed_plant_nana`, `seed_draw_jiu`) are outside the current manifest. The migration removes these only when their remaining relationships are Seed-only; if an ordinary account has interacted with one, it leaves that identity intact.

## Dataset and flow

The current dataset has ten account identities. Newly inserted accounts use password `1234`; existing accounts (including their passwords and profile choices) are never edited.

| Username | Name | Theme |
| --- | --- | --- |
| `seed_mori_cafe` | 김서윤 | Cafe visits |
| `seed_trip_min` | 최민재 | Travel |
| `seed_run_haru` | 이하루 | Running |
| `seed_fashion_roe` | 서로운 | Everyday fashion |
| `seed_dev_joon` | 박준호 | Development |
| `seed_pet_dodo` | 오도현 | Dog and walks |
| `seed_food_tae` | 강태윤 | Home cooking |
| `seed_music_ian` | 한이안 | Music |
| `seed_nature_nana` | 정나은 | Plants and nature |
| `seed_weekend_su` | 이수현 | Weekends with friends |

Each account gets 5–7 posts with two related images per post, 3–4 reels, and five active stories (four image stories and one video story). Post dates are spread across roughly three months; reels use varied dates, and story expiry is in the future. Likes, comments, reposts, friendships and notifications are linked to existing rows. The script checks required counts, media files, encoded video metadata, and expiry before committing.

The execution flow is:

```text
Parse CLI flags
  → connect to the configured database without schema bootstrap
  → inspect Seed ownership and print the reset plan
  → prepare/check Seed-specific media
  → optionally remove only the preflight-approved, marked Seed content and relationship rows
  → insert accounts, posts, reels, stories and relationships in one DB transaction
  → validate counts, foreign keys/uniqueness through the DB, file paths and video metadata
  → commit rows, then clean up unreferenced old Seed media after reset
```

## Media paths and deployment

Post and Story `media_url` values are paths relative to Flask's `static` directory, matching `url_for('static', filename=...)` and the project's media URL filter. A Post stores multiple images as a comma-separated list, as expected by the existing Post templates. Reel URLs and thumbnail URLs are basenames served from `/reels/uploads/...`.

Optimized JPEG photo sheets live under `story/static/seed_media/photo_sheets/` (about 4.6 MB total in this dataset). The seed script crops them into self-contained JPG files for profile, Post, and Story media. Earlier SVG viewports referenced a separate JPG sheet; browsers can block external resources in SVGs loaded through `<img>`, which caused the blank Post images. Reel and Story videos are generated as 9:16, 5–8 second H.264/AAC MP4s using the corresponding topic photograph with subtle camera motion. They are valid browser-playable MP4 files, but are generated motion clips from still photography rather than recorded live-action footage. `imageio-ffmpeg` supplies the FFmpeg encoder used by the seed script.

The lowercase `dockerfile` copies the project with `COPY . .`, so committed static Seed assets are included in a Docker image. `render.yaml` uses Render's Python runtime and installs `requirements.txt`; it does not build that Dockerfile. The static assets are included in the deployed source checkout. This does not make user uploads persistent on an ephemeral host; it only covers the bundled presentation assets.

## Post uploads

The Post composer accepts images only (`accept="image/*"`), checks image MIME types in the browser, and the server rejects non-image extensions/types in both local and signed-upload flows. The Post upload path stores images in the configured Post media location; video uploads belong to Reels or Stories.
