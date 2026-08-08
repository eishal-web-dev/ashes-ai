from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional


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
            config=Config(signature_version='s3v4'),
        )

    def put_file(self, source: Path, key: str, content_type: Optional[str] = None) -> str:
        extra = {'ContentType': content_type} if content_type else None
        if extra:
            self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra)
        else:
            self.client.upload_file(str(source), self.bucket, key)
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


def build_storage(local_root: Path, api_base_url: str) -> StorageBackend:
    provider = os.getenv('ASHES_STORAGE_PROVIDER', 'local').strip().lower()
    if provider in {'s3', 'r2', 'supabase-s3'}:
        return S3Storage()
    return LocalStorage(local_root, api_base_url)
