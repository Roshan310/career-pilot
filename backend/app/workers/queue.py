from redis import Redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()

# Without these a Redis outage doesn't fail — it hangs, holding the request open
# indefinitely while the user watches a spinner.
_REDIS_CONNECT_TIMEOUT_SECONDS = 3
_REDIS_OPERATION_TIMEOUT_SECONDS = 5

_redis_conn: Redis | None = None
_queue: Queue | None = None


def get_redis_connection() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_REDIS_OPERATION_TIMEOUT_SECONDS,
        )
    return _redis_conn


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue("default", connection=get_redis_connection())
    return _queue


def enqueue_matching_job(match_id: str) -> None:
    get_queue().enqueue("app.workers.jobs.run_matching_job", match_id)
