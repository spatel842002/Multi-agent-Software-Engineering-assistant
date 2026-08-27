from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

# In-process storage in tests: the fast test suite must never depend on a
# live Redis instance being up. Production/development use real Redis so
# rate limits are shared and durable across worker processes.
_storage_uri = "memory://" if settings.environment == "test" else settings.redis_url

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=[settings.rate_limit_default],
)
