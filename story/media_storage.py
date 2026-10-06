"""Supabase Storage uploads with local filesystem fallback for development."""

import mimetypes
import os
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app, url_for


def _storage_settings():
    project_url = os.environ.get('SUPABASE_URL')
    secret_key = os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if project_url and secret_key:
        return project_url.rstrip('/'), secret_key, os.environ.get('SUPABASE_STORAGE_BUCKET', 'story-media')
    if project_url or secret_key or os.environ.get('RENDER'):
        raise RuntimeError('Set SUPABASE_URL and SUPABASE_SECRET_KEY for persistent uploads.')
    return None


def upload_media(file_storage, folder, resource_type='image'):
    """Upload an asset and return a compact DB reference or local static URL."""
    original_name = getattr(file_storage, 'filename', None) or getattr(file_storage, 'name', None) or 'upload'
    settings = _storage_settings()

    if settings:
        base_url, service_key, bucket = settings
        object_key = secrets.token_urlsafe(16)
        content_type = (
            getattr(file_storage, 'mimetype', None)
            or mimetypes.guess_type(original_name)[0]
            or 'application/octet-stream'
        )
        body = file_storage.read()

        # 💡 인증 오류를 해결하기 위해 최신 Supabase 규격에 맞춰 헤더를 필수 고정 항목으로 수정했습니다.
        headers = {
            'apikey': service_key,
            'Content-Type': content_type,
            'x-upsert': 'false',
            'Authorization': f'Bearer {service_key}'
        }

        request = Request(
            f"{base_url}/storage/v1/object/{quote(bucket, safe='')}/{quote(object_key, safe='')}",
            data=body,
            headers=headers,
            method='POST',
        )
        try:
            with urlopen(request, timeout=60):
                pass
        except (HTTPError, URLError) as error:
            detail = error.read().decode('utf-8', errors='replace') if isinstance(error, HTTPError) else str(error)
            raise RuntimeError(f'Supabase Storage upload failed: {detail}') from error
        return f'sb:{object_key}'

    filename = f"{secrets.token_hex(16)}_{os.path.basename(original_name)}"
    if folder == 'story-posts':
        base = current_app.config['POST_UPLOAD_FOLDER']
        relative = os.path.join('photo', filename)
    elif folder == 'story-profiles':
        base = current_app.config['PROFILE_UPLOAD_FOLDER']
        relative = os.path.join('profile', filename)
    else:
        category = 'videos' if resource_type == 'video' else 'thumbnails'
        base = os.path.join(current_app.config['UPLOAD_FOLDER'], category)
        relative = os.path.join('reels_uploads', category, filename)
    os.makedirs(base, exist_ok=True)
    file_path = os.path.join(base, filename)
    file_storage.save(file_path)
    if folder == 'story-reels':
        return file_path
    return relative.replace('\\', '/')


def media_url(value):
    """Turn compact Supabase references and legacy paths into display URLs."""
    if not value:
        return ''
    value = str(value)
    if value.startswith('sb:'):
        settings = _storage_settings()
        if not settings:
            return ''
        base_url, _, bucket = settings
        return (
            f"{base_url}/storage/v1/object/public/{quote(bucket, safe='')}/"
            f"{quote(value[3:], safe='')}"
        )
    if value.startswith(('http://', 'https://', '/')):
        return value
    return url_for('static', filename=value)


def media_urls(value):
    return ','.join(media_url(part.strip()) for part in (value or '').split(',') if part.strip())
