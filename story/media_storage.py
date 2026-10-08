"""Supabase Storage uploads with local filesystem fallback for development."""

import mimetypes
import json
import os
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_MEDIA_CONTENT_TYPE_CACHE = {}

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
        extension = os.path.splitext(original_name)[1].lower()
        if not extension[1:].isalnum() or len(extension) > 11:
            extension = ''
        object_key = f'{secrets.token_urlsafe(16)}{extension}'

        guessed_type_tuple = mimetypes.guess_type(original_name)
        guessed_type = guessed_type_tuple[0] if guessed_type_tuple else None

        uploaded_type = getattr(file_storage, 'mimetype', None)
        content_type = (
            guessed_type if uploaded_type in (None, '', 'application/octet-stream') and guessed_type
            else uploaded_type or guessed_type or 'application/octet-stream'
        )

        # 💡 파일 데이터를 바이트 단위로 읽어옵니다.
        body = file_storage.read()
        if isinstance(body, str):
            body = body.encode('utf-8')

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


def create_signed_upload_url(object_key):
    """Create a one-time Supabase Storage URL for a browser-to-storage upload."""
    settings = _storage_settings()
    if not settings:
        return None

    base_url, service_key, bucket = settings
    encoded_path = '/'.join(quote(part, safe='') for part in object_key.split('/'))
    request = Request(
        f'{base_url}/storage/v1/object/upload/sign/{quote(bucket, safe="")}/{encoded_path}',
        data=b'{}',
        headers={
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError) as error:
        detail = error.read().decode('utf-8', errors='replace') if isinstance(error, HTTPError) else str(error)
        raise RuntimeError(f'Supabase Storage signed upload URL failed: {detail}') from error

    signed_path = payload.get('url')
    if not signed_path:
        raise RuntimeError('Supabase Storage did not return a signed upload URL.')
    return {
        'key': object_key,
        'url': f'{base_url}/storage/v1{signed_path}',
    }


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


def media_content_type(value):
    """Return a stored asset's MIME type, including legacy extensionless objects."""
    if not value:
        return ''
    value = str(value)
    guessed_type = mimetypes.guess_type(value)[0]
    if guessed_type:
        return guessed_type
    if not value.startswith('sb:'):
        return ''
    if value in _MEDIA_CONTENT_TYPE_CACHE:
        return _MEDIA_CONTENT_TYPE_CACHE[value]

    settings = _storage_settings()
    if not settings:
        return ''
    base_url, _, bucket = settings
    object_key = value[3:]
    object_url = (
        f"{base_url}/storage/v1/object/public/{quote(bucket, safe='')}/"
        f"{quote(object_key, safe='')}"
    )
    content_type = ''
    try:
        request = Request(object_url, method='HEAD')
        with urlopen(request, timeout=3) as response:
            content_type = response.headers.get_content_type()
    except (HTTPError, URLError, TimeoutError):
        pass
    _MEDIA_CONTENT_TYPE_CACHE[value] = content_type
    return content_type


def media_urls(value):
    return ','.join(media_url(part.strip()) for part in (value or '').split(',') if part.strip())
