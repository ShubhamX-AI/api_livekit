"""Direct S3 access for the audio asset library.

Recordings are uploaded by the LiveKit egress service (see livekit_svc.py), but
audio assets are uploaded by our API and downloaded by the worker, so we need a
direct S3 client here. boto3 is synchronous — callers in async code must wrap
these functions with asyncio.to_thread().
"""

import tempfile

import boto3

from src.core.config import settings
from src.core.logger import logger


_s3 = None


def _client():
    """Return a cached S3 client built from the configured AWS credentials."""
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    return _s3


def build_key(audio_id: str) -> str:
    """Return the S3 key for an audio asset's WAV."""
    return f"{settings.S3_GREETING_PREFIX}{audio_id}.wav"


def upload(audio_id: str, data: bytes) -> str:
    """Upload WAV bytes and return the stored S3 key."""
    key = build_key(audio_id)
    _client().put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType="audio/wav",
    )
    logger.info("Audio asset uploaded | audio=%s | key=%s", audio_id, key)
    return key


def download_to_tempfile(key: str) -> str:
    """Download the object to a temp WAV file and return its path. Caller deletes it."""
    obj = _client().get_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(obj["Body"].read())
        return tmp.name


def delete(key: str) -> None:
    """Delete the object from S3."""
    _client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    logger.info("Audio asset deleted | key=%s", key)


def presigned_get_url(key: str, expires: int = 3600) -> str:
    """Return a temporary download URL for the object."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=expires,
    )
