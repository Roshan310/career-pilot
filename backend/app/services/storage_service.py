import uuid

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()

_client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)


def ensure_bucket() -> None:
    """Idempotently create the resume storage bucket if it doesn't already exist."""
    try:
        _client.head_bucket(Bucket=settings.s3_bucket_name)
    except ClientError:
        _client.create_bucket(Bucket=settings.s3_bucket_name)


def upload_file(user_id: uuid.UUID, filename: str, content: bytes, content_type: str) -> str:
    """Upload a resume file to the private bucket (no public ACL — SPECS.md §9 PII
    requirement) and return its object key (stored as `resumes.file_url`)."""
    key = f"resumes/{user_id}/{uuid.uuid4()}-{filename}"
    _client.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=content, ContentType=content_type)
    return key


def get_signed_url(key: str, expires_in_seconds: int = 3600) -> str:
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expires_in_seconds,
    )


def delete_file(key: str) -> None:
    _client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
