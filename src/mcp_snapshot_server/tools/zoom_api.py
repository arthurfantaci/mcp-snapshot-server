"""Zoom API integration for MCP Snapshot Server.

This module provides functionality to interact with the Zoom API to list and download
meeting recordings and transcripts using Server-to-Server OAuth authentication.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import quote

import httpx
from cachetools import TTLCache

from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError, retry_on_error

logger = logging.getLogger(__name__)

# Zoom API base URL
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"


class ZoomAPIManager:
    """Manager for Zoom API with Server-to-Server OAuth and caching."""

    _instance: "ZoomAPIManager | None" = None
    _recordings_cache: TTLCache | None = None
    _access_token: str | None = None
    _token_expiry: datetime | None = None

    def __new__(cls) -> "ZoomAPIManager":
        """Implement singleton pattern for ZoomAPIManager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Zoom API manager."""
        if not hasattr(self, "_initialized"):
            self.settings = get_settings()
            self._initialized = True
            logger.info("ZoomAPIManager initialized")

    async def _get_access_token(self) -> str:
        """Get or refresh Server-to-Server OAuth access token.

        Returns:
            Valid access token

        Raises:
            MCPServerError: If token request fails
        """
        # Check if we have a valid cached token
        if (
            self._access_token
            and self._token_expiry
            and datetime.now() < self._token_expiry
        ):
            return self._access_token

        # Request new token
        token_url = "https://zoom.us/oauth/token"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    params={
                        "grant_type": "account_credentials",
                        "account_id": self.settings.zoom.account_id,
                    },
                    auth=(
                        self.settings.zoom.client_id,
                        self.settings.zoom.client_secret,
                    ),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()

                data = response.json()
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)  # Default 1 hour

                # Set expiry to 5 minutes before actual expiry for safety
                self._token_expiry = datetime.now() + timedelta(
                    seconds=expires_in - 300
                )

                logger.info(
                    f"Obtained new Zoom access token (expires in {expires_in}s)"
                )
                return self._access_token

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting Zoom token: {e.response.status_code}")
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_AUTH_ERROR,
                message=f"Failed to authenticate with Zoom: HTTP {e.response.status_code}",
                details={
                    "status_code": e.response.status_code,
                    "response": e.response.text,
                },
            ) from e
        except Exception as e:
            logger.error(f"Failed to get Zoom access token: {e}")
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_AUTH_ERROR,
                message=f"Failed to authenticate with Zoom: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def api_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated API request to Zoom.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/users/me/recordings")
            params: URL query parameters
            json_data: JSON request body

        Returns:
            JSON response from API

        Raises:
            MCPServerError: If request fails
        """
        # Validate credentials are configured
        if not all(
            [
                self.settings.zoom.account_id,
                self.settings.zoom.client_id,
                self.settings.zoom.client_secret,
            ]
        ):
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_NOT_CONFIGURED,
                message="Zoom API credentials not configured. Set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET.",
                details={
                    "has_account_id": bool(self.settings.zoom.account_id),
                    "has_client_id": bool(self.settings.zoom.client_id),
                    "has_client_secret": bool(self.settings.zoom.client_secret),
                },
            )

        # Get valid access token
        access_token = await self._get_access_token()

        # Build full URL
        url = f"{ZOOM_API_BASE_URL}{endpoint}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=self.settings.zoom.api_timeout,
                )
                response.raise_for_status()
                return cast("dict[str, Any]", response.json())

        except httpx.HTTPStatusError as e:
            # Try to parse Zoom's error response
            error_details = {
                "endpoint": endpoint,
                "status_code": e.response.status_code,
                "response": e.response.text,
            }

            try:
                error_json = e.response.json()
                zoom_error_code = error_json.get("code")
                zoom_error_msg = error_json.get("message", "")
                error_details["zoom_error_code"] = zoom_error_code
                error_details["zoom_error_message"] = zoom_error_msg

                # Create a more helpful error message
                error_message = f"Zoom API error {e.response.status_code}"
                if zoom_error_code:
                    error_message += f" (code: {zoom_error_code})"
                if zoom_error_msg:
                    error_message += f": {zoom_error_msg}"
            except Exception:
                # If we can't parse JSON, use the raw response
                error_message = (
                    f"Zoom API request failed: HTTP {e.response.status_code}"
                )

            logger.error(
                error_message,
                extra={"status_code": e.response.status_code, "endpoint": endpoint},
            )

            raise MCPServerError(
                error_code=ErrorCode.ZOOM_API_ERROR,
                message=error_message,
                details=error_details,
            ) from e
        except Exception as e:
            logger.error(f"Zoom API request failed: {e}")
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_API_ERROR,
                message=f"Zoom API request failed: {str(e)}",
                details={
                    "endpoint": endpoint,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

    @property
    def recordings_cache(self) -> TTLCache:
        """Get or create recordings cache.

        Returns:
            TTL cache for recordings
        """
        if self._recordings_cache is None:
            ttl = self.settings.zoom.cache_ttl_seconds
            maxsize = self.settings.zoom.max_cache_size
            self._recordings_cache = TTLCache(maxsize=maxsize, ttl=ttl)
            logger.info(
                f"Recordings cache initialized (TTL: {ttl}s, max size: {maxsize})"
            )

        return self._recordings_cache

    def _get_cache_key(self, from_date: str | None, to_date: str | None) -> str:
        """Generate cache key for recordings list.

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Cache key string
        """
        user_id = self.settings.zoom.default_user_id
        return f"recordings_{user_id}_{from_date}_{to_date}"


@retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
async def list_user_recordings(
    manager: ZoomAPIManager,
    from_date: str | None = None,
    to_date: str | None = None,
    page_size: int = 30,
    has_transcript: bool = True,
) -> dict[str, Any]:
    """List Zoom cloud recordings for the configured user.

    Args:
        manager: ZoomAPIManager instance
        from_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        to_date: End date (YYYY-MM-DD). Defaults to today.
        page_size: Number of recordings per page (max 300)
        has_transcript: Filter to only recordings with transcripts

    Returns:
        Dictionary with recordings list and metadata

    Raises:
        MCPServerError: If API request fails
    """
    settings = manager.settings

    # Set default date range if not provided
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")

    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    logger.info(
        "Listing Zoom recordings",
        extra={
            "from_date": from_date,
            "to_date": to_date,
            "page_size": page_size,
            "has_transcript": has_transcript,
        },
    )

    # Check cache first
    cache_key = manager._get_cache_key(from_date, to_date)
    if cache_key in manager.recordings_cache:
        logger.info("Returning cached recordings list", extra={"cache_key": cache_key})
        return cast("dict[str, Any]", manager.recordings_cache[cache_key])

    try:
        # Make API request to list recordings
        user_id = settings.zoom.default_user_id
        endpoint = f"/users/{user_id}/recordings"

        response = await manager.api_request(
            method="GET",
            endpoint=endpoint,
            params={
                "from": from_date,
                "to": to_date,
                "page_size": page_size,
            },
        )

        # Extract meetings from response
        meetings = response.get("meetings", [])

        logger.info(
            f"Fetched {len(meetings)} recordings from Zoom",
            extra={"from_date": from_date, "to_date": to_date},
        )

        # Filter for transcripts if requested
        if has_transcript:
            meetings = filter_recordings_with_transcripts(meetings)
            logger.info(
                f"Filtered to {len(meetings)} recordings with transcripts",
                extra={"has_transcript": True},
            )

        result = {
            "meetings": meetings,
            "from_date": from_date,
            "to_date": to_date,
            "total_count": len(meetings),
            "has_transcript_filter": has_transcript,
        }

        # Cache the result
        manager.recordings_cache[cache_key] = result

        return result

    except Exception as e:
        logger.error(
            f"Failed to list Zoom recordings: {e}",
            extra={"error_type": type(e).__name__},
        )
        raise MCPServerError(
            error_code=ErrorCode.ZOOM_API_ERROR,
            message=f"Failed to list Zoom recordings: {str(e)}",
            details={
                "from_date": from_date,
                "to_date": to_date,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        ) from e


def encode_meeting_id(meeting_id: str) -> str:
    """Encode meeting ID according to Zoom API requirements.

    Zoom API encoding rules:
    - Numeric IDs: No encoding needed
    - UUIDs with '/' or '//': Double URL-encode
    - UUIDs with other special characters: Single URL-encode

    Args:
        meeting_id: Meeting ID or UUID

    Returns:
        Properly encoded meeting ID
    """
    meeting_id_str = str(meeting_id).strip()

    # If it's a numeric ID, no encoding needed
    if meeting_id_str.isdigit():
        return meeting_id_str

    # If UUID contains / or //, use double encoding
    if "/" in meeting_id_str:
        return quote(quote(meeting_id_str, safe=""), safe="")

    # For other UUIDs with special characters, use single encoding
    return quote(meeting_id_str, safe="")


@retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
async def get_meeting_recordings(
    manager: ZoomAPIManager, meeting_id: str
) -> dict[str, Any]:
    """Get recording files for a specific Zoom meeting.

    Args:
        manager: ZoomAPIManager instance
        meeting_id: Zoom meeting ID or UUID (will be URL-encoded as needed)

    Returns:
        Dictionary with meeting recording details

    Raises:
        MCPServerError: If API request fails or meeting not found
    """
    logger.info("Fetching meeting recordings", extra={"meeting_id": meeting_id})

    try:
        # Encode meeting ID according to Zoom API requirements
        encoded_meeting_id = encode_meeting_id(meeting_id)

        logger.debug(
            "Encoded meeting ID",
            extra={"original": meeting_id, "encoded": encoded_meeting_id},
        )

        # Make API request to get meeting recordings
        endpoint = f"/meetings/{encoded_meeting_id}/recordings"

        response = await manager.api_request(
            method="GET",
            endpoint=endpoint,
        )

        logger.info(
            "Fetched meeting recordings successfully",
            extra={
                "meeting_id": meeting_id,
                "recording_count": len(response.get("recording_files", [])),
            },
        )

        return response

    except MCPServerError:
        # Re-raise MCPServerError to preserve detailed error information
        raise
    except Exception as e:
        logger.error(
            f"Failed to get meeting recordings: {e}",
            extra={"meeting_id": meeting_id, "error_type": type(e).__name__},
        )
        raise MCPServerError(
            error_code=ErrorCode.ZOOM_API_ERROR,
            message=f"Failed to get meeting recordings: {str(e)}",
            details={
                "meeting_id": meeting_id,
                "encoded_id": encode_meeting_id(meeting_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        ) from e


@retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
async def download_transcript_content(
    download_url: str, access_token: str, timeout: int = 30
) -> str:
    """Download VTT transcript content from Zoom.

    Args:
        download_url: URL to download transcript from
        access_token: Zoom API access token
        timeout: Request timeout in seconds

    Returns:
        VTT transcript content as string

    Raises:
        MCPServerError: If download fails
    """
    logger.info(
        "Downloading transcript content", extra={"url_length": len(download_url)}
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()

            content = response.text

            logger.info(
                "Transcript downloaded successfully",
                extra={"content_length": len(content)},
            )

            return content

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error downloading transcript: {e.response.status_code}",
            extra={"status_code": e.response.status_code},
        )
        raise MCPServerError(
            error_code=ErrorCode.ZOOM_API_ERROR,
            message=f"Failed to download transcript: HTTP {e.response.status_code}",
            details={
                "status_code": e.response.status_code,
                "error": str(e),
            },
        ) from e

    except httpx.TimeoutException as e:
        logger.error("Timeout downloading transcript")
        raise MCPServerError(
            error_code=ErrorCode.TIMEOUT,
            message="Timeout downloading transcript from Zoom",
            details={"timeout": timeout, "error": str(e)},
        ) from e

    except Exception as e:
        logger.error(
            f"Failed to download transcript: {e}",
            extra={"error_type": type(e).__name__},
        )
        raise MCPServerError(
            error_code=ErrorCode.ZOOM_API_ERROR,
            message=f"Failed to download transcript: {str(e)}",
            details={"error": str(e), "error_type": type(e).__name__},
        ) from e


def filter_recordings_with_transcripts(
    meetings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter recordings to only those with VTT transcript files.

    Args:
        meetings: List of meeting recording objects

    Returns:
        Filtered list of meetings with transcripts
    """
    filtered = []

    for meeting in meetings:
        recording_files = meeting.get("recording_files", [])

        # Check if any recording file is a VTT transcript
        has_vtt = any(
            file.get("file_type") == "TRANSCRIPT"
            and file.get("file_extension") == "VTT"
            for file in recording_files
        )

        if has_vtt:
            filtered.append(meeting)

    return filtered


def search_recordings_by_topic(
    meetings: list[dict[str, Any]], search_query: str
) -> list[dict[str, Any]]:
    """Filter recordings by topic/title search.

    Args:
        meetings: List of meeting recording objects
        search_query: Search query (case-insensitive substring match)

    Returns:
        Filtered list of meetings matching the search query
    """
    if not search_query:
        return meetings

    query_lower = search_query.lower()
    filtered = []

    for meeting in meetings:
        topic = meeting.get("topic", "").lower()
        if query_lower in topic:
            filtered.append(meeting)

    logger.info(
        f"Topic search filtered to {len(filtered)} meetings",
        extra={"query": search_query, "original_count": len(meetings)},
    )

    return filtered


def find_transcript_file(
    recording_files: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find VTT transcript file in recording files list.

    Args:
        recording_files: List of recording file objects

    Returns:
        Transcript file object or None if not found
    """
    for file in recording_files:
        if (
            file.get("file_type") == "TRANSCRIPT"
            and file.get("file_extension") == "VTT"
        ):
            return file

    return None
