from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse


class StorageBackend:
    def put_file(self, source: Path, key: str, content_type: Optional[str] = None) -> str:
        raise NotImplementedError

    def delete(self, key_or_path: str) -> None:
        raise NotImplementedError

    def public_url(self, key_or_path: str) -> str:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, root: Path, api_base_url: str):
        self.root = root
        self.api_base_url = api_base_url.rstrip('/')
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, source: Path, key: str, content_type: Optional[str] = None) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return str(target)

    def delete(self, key_or_path: str) -> None:
        path = Path(key_or_path)
        if not path.is_absolute():
            path = self.root / key_or_path
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def public_url(self, key_or_path: str) -> str:
        path = Path(key_or_path)
        try:
            relative = path.resolve().relative_to(self.root.resolve()).as_posix()
        except Exception:
            relative = path.name
        return f"{self.api_base_url}/media/storage/{relative}"


class S3Storage(StorageBackend):
    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = os.environ['ASHES_S3_BUCKET']
        self.public_base_url = os.getenv('ASHES_S3_PUBLIC_BASE_URL', '').rstrip('/')
        endpoint_url = os.getenv('ASHES_S3_ENDPOINT_URL') or None
        region = os.getenv('ASHES_S3_REGION') or 'auto'
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=os.getenv('ASHES_S3_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('ASHES_S3_SECRET_ACCESS_KEY'),
            config=Config(
                signature_version='s3v4',
                request_checksum_calculation='when_required',
                response_checksum_validation='when_required',
                s3={'addressing_style': 'path'},
            ),
        )

    def put_file(self, source: Path, key: str, content_type: Optional[str] = None) -> str:
        # Supabase's S3-compatible endpoint supports standard PutObject. Using a
        # direct single-request upload avoids boto3's managed-transfer extras
        # (multipart/checksum negotiation) that some S3-compatible providers do
        # not implement exactly like AWS S3.
        kwargs = {
            'Bucket': self.bucket,
            'Key': key,
            'Body': source.read_bytes(),
        }
        if content_type:
            kwargs['ContentType'] = content_type
        self.client.put_object(**kwargs)
        return key

    def delete(self, key_or_path: str) -> None:
        key = str(key_or_path).lstrip('/')
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def public_url(self, key_or_path: str) -> str:
        key = str(key_or_path).lstrip('/')
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        endpoint = os.getenv('ASHES_S3_ENDPOINT_URL', '').rstrip('/')
        if endpoint:
            return f"{endpoint}/{self.bucket}/{key}"
        region = os.getenv('ASHES_S3_REGION', 'us-east-1')
        return f"https://{self.bucket}.s3.{region}.amazonaws.com/{key}"


class SupabaseStorage(StorageBackend):
    def __init__(self):
        import requests

        self.requests = requests
        raw = (os.getenv('SUPABASE_URL') or os.getenv('ASHES_S3_ENDPOINT_URL') or '').rstrip('/')
        if not raw:
            raise RuntimeError('Supabase URL is not configured')
        parsed = urlparse(raw)
        host = parsed.hostname or ''
        if host.endswith('.storage.supabase.co'):
            project_ref = host.removesuffix('.storage.supabase.co')
            self.base_url = f"https://{project_ref}.supabase.co"
        else:
            self.base_url = f"{parsed.scheme or 'https'}://{host}" if host else raw
        self.service_key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
        self.bucket = os.environ['SUPABASE_STORAGE_BUCKET']

    def _headers(self, content_type: Optional[str] = None) -> dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.service_key}',
            'apikey': self.service_key,
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    def _object_url(self, key: str) -> str:
        bucket = quote(self.bucket, safe='')
        encoded_key = '/'.join(quote(part, safe='') for part in key.lstrip('/').split('/'))
        return f"{self.base_url}/storage/v1/object/{bucket}/{encoded_key}"

    def put_file(self, source: Path, key: str, content_type: Optional[str] = None) -> str:
        with source.open('rb') as handle:
            response = self.requests.post(
                self._object_url(key),
                headers={**self._headers(content_type or 'application/octet-stream'), 'x-upsert': 'true'},
                data=handle,
                timeout=120,
            )
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Supabase storage upload failed ({response.status_code}): {response.text[:400]}")
        return key.lstrip('/')

    def delete(self, key_or_path: str) -> None:
        key = str(key_or_path).lstrip('/')
        response = self.requests.delete(self._object_url(key), headers=self._headers(), timeout=30)
        if response.status_code not in {200, 204, 404}:
            raise RuntimeError(f"Supabase storage delete failed ({response.status_code}): {response.text[:250]}")

    def public_url(self, key_or_path: str) -> str:
        key = str(key_or_path).lstrip('/')
        bucket = quote(self.bucket, safe='')
        encoded_key = '/'.join(quote(part, safe='') for part in key.split('/'))
        return f"{self.base_url}/storage/v1/object/public/{bucket}/{encoded_key}"


def build_storage(local_root: Path, api_base_url: str) -> StorageBackend:
    provider = os.getenv('ASHES_STORAGE_PROVIDER', 'local').strip().lower()
    if provider == 'supabase':
        return SupabaseStorage()
    if provider in {'s3', 'r2', 'supabase-s3'}:
        return S3Storage()
    return LocalStorage(local_root, api_base_url)
