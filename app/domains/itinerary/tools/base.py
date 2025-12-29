"""Base classes and utilities for LangChain Tools."""

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Base exception for tool errors."""

    def __init__(self, message: str, tool_name: str, details: dict | None = None):
        self.message = message
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(self.message)


class APIClientError(ToolError):
    """Exception for API client errors."""

    pass


class RateLimitError(ToolError):
    """Exception for rate limit errors."""

    pass


class AuthenticationError(ToolError):
    """Exception for authentication errors."""

    pass


class BaseAsyncAPIClient(ABC):
    """Base class for async API clients with common functionality."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseAsyncAPIClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=await self._get_headers(),
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests. Override in subclasses."""
        pass

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        """Make an async HTTP request with retry logic."""
        if not self._client:
            raise APIClientError(
                "Client not initialized. Use async context manager.",
                tool_name=self.__class__.__name__,
            )

        url = f"{endpoint}" if endpoint.startswith("/") else f"/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    **kwargs,
                )

                if response.status_code == 401:
                    raise AuthenticationError(
                        "Authentication failed",
                        tool_name=self.__class__.__name__,
                    )

                if response.status_code == 429:
                    raise RateLimitError(
                        "Rate limit exceeded",
                        tool_name=self.__class__.__name__,
                    )

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = APIClientError(
                    f"HTTP error: {e.response.status_code}",
                    tool_name=self.__class__.__name__,
                    details={"status_code": e.response.status_code},
                )
                if e.response.status_code < 500:
                    raise last_error
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}")

            except httpx.RequestError as e:
                last_error = APIClientError(
                    f"Request error: {str(e)}",
                    tool_name=self.__class__.__name__,
                )
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}")

        if last_error:
            raise last_error
        raise APIClientError(
            "Max retries exceeded",
            tool_name=self.__class__.__name__,
        )

    async def get(
        self, endpoint: str, params: dict | None = None, **kwargs: Any
    ) -> dict:
        """Make an async GET request."""
        return await self._request("GET", endpoint, params=params, **kwargs)

    async def post(
        self,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        """Make an async POST request."""
        return await self._request(
            "POST", endpoint, params=params, json_data=json_data, **kwargs
        )


class CacheableResult(BaseModel):
    """Base class for cacheable API results."""

    cached: bool = False
    cache_key: str | None = None
    fetched_at: str | None = None
