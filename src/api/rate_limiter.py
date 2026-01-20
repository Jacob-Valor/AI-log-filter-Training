"""
Rate Limiting Middleware for FastAPI

Provides configurable rate limiting to protect the API from abuse
and ensure fair resource allocation.
"""

from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from src.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Rate Limit Configuration
# =============================================================================


class RateLimitConfig:
    """Configuration for rate limiting."""

    # Default limits (requests per time window)
    DEFAULT_LIMIT = "100/minute"

    # Endpoint-specific limits
    CLASSIFY_SINGLE_LIMIT = "60/minute"
    CLASSIFY_BATCH_LIMIT = "30/minute"
    HEALTH_LIMIT = "120/minute"
    FEEDBACK_LIMIT = "20/minute"

    # Burst limits (for short-term spikes)
    BURST_LIMIT = "10/second"

    # Exempt paths (no rate limiting)
    EXEMPT_PATHS = [
        "/health/live",
        "/metrics",
    ]

    # Headers to check for client identification
    CLIENT_ID_HEADERS = [
        "X-API-Key",
        "X-Client-ID",
        "Authorization",
    ]


# =============================================================================
# Custom Key Functions
# =============================================================================


def get_client_identifier(request: Request) -> str:
    """
    Get a unique identifier for the client.

    Priority:
    1. API Key header
    2. Client ID header
    3. Authorization header (hashed)
    4. Remote IP address
    """
    # Check for API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key[:16]}"  # Use prefix only for privacy

    # Check for client ID
    client_id = request.headers.get("X-Client-ID")
    if client_id:
        return f"client:{client_id}"

    # Check for auth header (use hash for privacy)
    auth_header = request.headers.get("Authorization")
    if auth_header:
        import hashlib

        auth_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
        return f"auth:{auth_hash}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


def get_ip_address(request: Request) -> str:
    """Get client IP address with proxy support."""
    # Check X-Forwarded-For header (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the list is the original client
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection IP
    return get_remote_address(request)


# =============================================================================
# Limiter Setup
# =============================================================================

# Create limiter instance
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=[RateLimitConfig.DEFAULT_LIMIT],
    headers_enabled=True,  # Include rate limit headers in response
    strategy="fixed-window",  # Use fixed window strategy
)


def get_limiter() -> Limiter:
    """Get the limiter instance for use in FastAPI app."""
    return limiter


# =============================================================================
# Rate Limit Decorators
# =============================================================================


def rate_limit(limit: str = RateLimitConfig.DEFAULT_LIMIT):
    """
    Decorator to apply rate limiting to an endpoint.

    Usage:
        @app.get("/endpoint")
        @rate_limit("30/minute")
        async def my_endpoint():
            ...
    """
    return limiter.limit(limit)


def rate_limit_by_ip(limit: str = RateLimitConfig.DEFAULT_LIMIT):
    """Rate limit by IP address specifically."""
    return limiter.limit(limit, key_func=get_ip_address)


# =============================================================================
# Custom Exception Handler
# =============================================================================


async def custom_rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> Response:
    """
    Custom handler for rate limit exceeded errors.

    Returns a JSON response with details about the rate limit.
    """
    # Log the rate limit event
    client_id = get_client_identifier(request)
    logger.warning(
        f"Rate limit exceeded for {client_id}",
        extra={
            "client_id": client_id,
            "path": request.url.path,
            "method": request.method,
            "limit": str(exc.detail),
        },
    )

    # Return structured error response
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": str(exc.detail),
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": request.headers.get("X-RateLimit-Limit", "unknown"),
            "X-RateLimit-Remaining": "0",
        },
    )


# =============================================================================
# Middleware Setup Helper
# =============================================================================


def setup_rate_limiting(app):
    """
    Set up rate limiting for a FastAPI application.

    Usage:
        from src.api.rate_limiter import setup_rate_limiting

        app = FastAPI()
        setup_rate_limiting(app)
    """
    # Attach limiter to app state
    app.state.limiter = limiter

    # Add rate limit exceeded handler
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

    # Add middleware
    app.add_middleware(SlowAPIMiddleware)

    logger.info(
        "Rate limiting enabled",
        extra={
            "default_limit": RateLimitConfig.DEFAULT_LIMIT,
            "classify_limit": RateLimitConfig.CLASSIFY_SINGLE_LIMIT,
            "batch_limit": RateLimitConfig.CLASSIFY_BATCH_LIMIT,
        },
    )


# =============================================================================
# Rate Limit Status Endpoint Helper
# =============================================================================


async def get_rate_limit_status(request: Request) -> dict:
    """
    Get current rate limit status for a client.

    Returns information about remaining requests and reset time.
    """
    client_id = get_client_identifier(request)

    # Get rate limit headers from response (if available)
    return {
        "client_id": client_id,
        "limits": {
            "classify": RateLimitConfig.CLASSIFY_SINGLE_LIMIT,
            "classify_batch": RateLimitConfig.CLASSIFY_BATCH_LIMIT,
            "default": RateLimitConfig.DEFAULT_LIMIT,
        },
        "note": "Check X-RateLimit-* headers in responses for current usage",
    }
