import logging

import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from src.constants import PROXY_EXCLUDED_REQUEST_HEADERS, PROXY_EXCLUDED_RESPONSE_HEADERS

logger = logging.getLogger(__name__)


async def proxy(
    request: Request,
    proxy_url: str,
    proxy_host: str,
    proxy_port: int,
    proxy_path: str,
) -> Response:

    # Extract path parameter if present, otherwise use root
    req_path = request.path_params.get("path")
    if req_path is None:
        req_path = "/"
    elif not req_path.startswith("/"):
        req_path = f"/{req_path}"

    # Build target URL
    # ch_settings = get_clickhouse_settings()
    # ch_http_url = ch_settings.http_url
    target_url = f"{proxy_url}{req_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Prepare headers for proxying
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() not in PROXY_EXCLUDED_REQUEST_HEADERS:
            headers[key] = value

    # Update Host header to target
    headers["Host"] = f"{proxy_host}:{proxy_port}"

    # Get request body if present
    body: bytes | None = None
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 0:
        body = await request.body()

    try:
        # Make request to ClickHouse
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False,
            )

            # Prepare response headers
            response_headers: dict[str, str] = {}
            for key, value in response.headers.items():
                if key.lower() not in PROXY_EXCLUDED_RESPONSE_HEADERS:
                    response_headers[key] = value

            # Handle redirects
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if location.startswith(proxy_url):
                    # Rewrite redirect location to use proxy path
                    location = location.replace(proxy_url, proxy_path)
                    response_headers["location"] = location

            # Create streaming response for large content
            if response.headers.get("content-type", "").startswith("text/"):
                # For text content, read all at once
                content = response.content
                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers,
                )
            else:
                # For binary content, stream it
                return StreamingResponse(
                    response.iter_bytes(),
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type"),
                )

    except httpx.TimeoutException:
        logger.error("[CH-Proxy] Timeout connecting to ClickHouse UI")
        return Response(
            content=b"ClickHouse UI timeout",
            status_code=503,
            headers={"content-type": "text/plain"},
        )
    except httpx.ConnectError as e:
        logger.error("[CH-Proxy] Failed to connect to ClickHouse UI: %r", e)
        return Response(
            content=b"ClickHouse UI unavailable",
            status_code=503,
            headers={"content-type": "text/plain"},
        )
    except Exception as e:
        logger.error("[CH-Proxy] Unexpected error proxying to ClickHouse UI: %r", e)
        return Response(
            content=b"Internal proxy error",
            status_code=500,
            headers={"content-type": "text/plain"},
        )
