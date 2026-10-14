"""Evidence storage: local filesystem (dev/tests) or S3/MinIO (Object Lock bucket)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from ..core.config import get_settings

EXT = {"image/jpeg": "jpg", "image/png": "png", "image/bmp": "bmp"}


def object_key(kind: str, sha256: str, mime: str, when: datetime) -> str:
    return f"{kind.lower()}/{when:%Y/%m/%d}/{sha256}.{EXT.get(mime, 'bin')}"


class Storage(Protocol):
    def put(self, key: str, data: bytes, mime: str) -> str: ...
    def get(self, uri: str) -> bytes: ...
    def overwrite(self, uri: str, data: bytes) -> None: ...  # Tamper Lab only


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    def put(self, key: str, data: bytes, mime: str) -> str:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(data)
        return f"file://{key}"

    def _path(self, uri: str) -> Path:
        assert uri.startswith("file://"), uri
        return self.root / uri[len("file://"):]

    def get(self, uri: str) -> bytes:
        return self._path(uri).read_bytes()

    def overwrite(self, uri: str, data: bytes) -> None:
        self._path(uri).write_bytes(data)


class S3Storage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key,
                               aws_secret_access_key=secret_key, region_name="us-east-1")

    def put(self, key: str, data: bytes, mime: str) -> str:
        import hashlib

        md5 = __import__("base64").b64encode(hashlib.md5(data).digest()).decode()  # required by Object Lock
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime, ContentMD5=md5)
        return f"s3://{self.bucket}/{key}"

    def _split(self, uri: str) -> tuple[str, str]:
        rest = uri[len("s3://"):]
        bucket, key = rest.split("/", 1)
        return bucket, key

    def get(self, uri: str) -> bytes:
        b, k = self._split(uri)
        return self.s3.get_object(Bucket=b, Key=k)["Body"].read()

    def overwrite(self, uri: str, data: bytes) -> None:
        # With Object Lock the original version is retained; the new version becomes "latest".
        b, k = self._split(uri)
        self.put(k, data, "application/octet-stream")


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage(s.s3_endpoint, s.s3_access_key, s.s3_secret_key, s.s3_bucket)
    return LocalStorage(s.storage_dir)
