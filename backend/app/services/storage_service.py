import logging
import re
import uuid

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Anything outside this gets collapsed to "_". The uuid prefix already makes keys
# unique, so this is about keeping object keys readable and free of path
# separators rather than about collision avoidance.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_FILENAME_LENGTH = 120


def safe_filename(filename: str | None, *, fallback: str = "resume") -> str:
    """A filename that is safe to embed in an object key.

    `UploadFile.filename` is `str | None` — a multipart part without one is
    legal, and it used to reach `extract_text`'s `"." in filename` as a TypeError
    (a 500). Directory separators and traversal segments are stripped because
    this value is concatenated into an S3 key and echoed back as
    `resumes.file_name`.
    """
    name = (filename or "").strip().replace("\\", "/").split("/")[-1]
    name = _UNSAFE_FILENAME_CHARS.sub("_", name).strip("._")
    if not name:
        return fallback
    return name[-_MAX_FILENAME_LENGTH:]

_client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)


def ensure_bucket() -> None:
    """Idempotently create the resume storage bucket if it doesn't already exist.

    Only a genuine 404 means "create it". Catching every ClientError treated a
    403 from bad credentials as a missing bucket, so startup went on to attempt a
    create that failed with an error naming the wrong problem entirely — the real
    cause (a bad S3 key) never appeared anywhere.
    """
    try:
        _client.head_bucket(Bucket=settings.s3_bucket_name)
        return
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            logger.error(
                "Cannot access bucket %s (HTTP %s). Check S3 credentials and endpoint.",
                settings.s3_bucket_name,
                status,
            )
            raise

    try:
        _client.create_bucket(Bucket=settings.s3_bucket_name)
        logger.info("Created bucket %s", settings.s3_bucket_name)
    except ClientError as exc:
        # Another worker booting concurrently is a normal race, not a failure.
        if exc.response.get("Error", {}).get("Code") in {
            "BucketAlreadyOwnedByYou",
            "BucketAlreadyExists",
        }:
            return
        raise


def upload_file(user_id: uuid.UUID, filename: str, content: bytes, content_type: str) -> str:
    """Upload a resume file to the private bucket (no public ACL — SPECS.md §9 PII
    requirement) and return its object key (stored as `resumes.file_url`)."""
    key = f"resumes/{user_id}/{uuid.uuid4()}-{filename}"
    _client.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=content, ContentType=content_type)
    return key


def upload_bytes(key: str, content: bytes, content_type: str) -> None:
    """Store an object at an exact, caller-chosen key. Unlike `upload_file`, which
    mints a random key per upload, this is for content that has a natural identity
    and gets looked up again — generated question audio, keyed by session and
    turn, so replaying a question doesn't re-bill the TTS vendor."""
    _client.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=content, ContentType=content_type)


def get_bytes(key: str) -> bytes | None:
    """The object's contents, or None if it isn't there. A cache miss is an
    ordinary outcome here, not an error, so it doesn't raise."""
    try:
        return _client.get_object(Bucket=settings.s3_bucket_name, Key=key)["Body"].read()
    except ClientError:
        return None


def get_signed_url(key: str, expires_in_seconds: int = 3600) -> str:
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expires_in_seconds,
    )


def delete_file(key: str) -> None:
    _client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
