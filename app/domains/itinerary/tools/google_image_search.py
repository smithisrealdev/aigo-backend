"""
MCP Tool for Google Custom Search Image API.

Fetches relevant images for locations, activities, and destinations.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageSearchResult(BaseModel):
    """Single image search result."""

    url: str
    thumbnail_url: str
    width: int | None = None
    height: int | None = None
    source_url: str | None = None
    source_domain: str | None = None
    title: str | None = None


class ImageSearchResponse(BaseModel):
    """Response from image search."""

    query: str
    images: list[ImageSearchResult]
    total_results: int | None = None
    search_time_ms: float | None = None


# In-memory cache (use Redis in production)
_image_cache: dict[str, tuple[ImageSearchResponse, datetime]] = {}


def _get_cache_key(query: str, num_images: int) -> str:
    """Generate cache key for query."""
    return hashlib.md5(f"{query}:{num_images}".encode()).hexdigest()


def _get_cached_result(cache_key: str) -> ImageSearchResponse | None:
    """Get cached result if valid."""
    if cache_key in _image_cache:
        result, cached_at = _image_cache[cache_key]
        ttl = settings.GOOGLE_IMAGE_CACHE_TTL
        if datetime.now() - cached_at < timedelta(seconds=ttl):
            return result
        else:
            del _image_cache[cache_key]
    return None


def _set_cached_result(cache_key: str, result: ImageSearchResponse) -> None:
    """Cache the result."""
    _image_cache[cache_key] = (result, datetime.now())


async def search_images(
    query: str,
    num_images: int = 5,
    image_size: str = "large",
    image_type: str = "photo",
    safe_search: str = "high",
) -> ImageSearchResponse:
    """
    Search for images using Google Custom Search API.

    Args:
        query: Search query (e.g., "Senso-ji Temple Tokyo")
        num_images: Number of images to return (1-10)
        image_size: Image size filter (small, medium, large, xlarge)
        image_type: Image type filter (photo, face, clipart, lineart)
        safe_search: Safe search level (off, medium, high)

    Returns:
        ImageSearchResponse with list of images
    """
    if not settings.GOOGLE_IMAGE_SEARCH_ENABLED:
        logger.warning("Google Image Search is disabled")
        return ImageSearchResponse(query=query, images=[])

    if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_CX:
        logger.error("Google Search API credentials not configured")
        return ImageSearchResponse(query=query, images=[])

    # Check cache first
    cache_key = _get_cache_key(query, num_images)
    cached = _get_cached_result(cache_key)
    if cached:
        logger.debug(f"Image search cache hit for: {query}")
        return cached

    # Build request
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": settings.GOOGLE_SEARCH_API_KEY,
        "cx": settings.GOOGLE_SEARCH_CX,
        "q": query,
        "searchType": "image",
        "num": min(num_images, 10),
        "imgSize": image_size,
        "imgType": image_type,
        "safe": safe_search,
    }

    try:
        start_time = datetime.now()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        # Parse results
        images: list[ImageSearchResult] = []
        for item in data.get("items", []):
            image_data = item.get("image", {})
            images.append(
                ImageSearchResult(
                    url=item.get("link", ""),
                    thumbnail_url=image_data.get(
                        "thumbnailLink", item.get("link", "")
                    ),
                    width=image_data.get("width"),
                    height=image_data.get("height"),
                    source_url=image_data.get("contextLink"),
                    source_domain=item.get("displayLink"),
                    title=item.get("title"),
                )
            )

        result = ImageSearchResponse(
            query=query,
            images=images,
            total_results=int(
                data.get("searchInformation", {}).get("totalResults", 0)
            ),
            search_time_ms=search_time,
        )

        # Cache the result
        _set_cached_result(cache_key, result)

        logger.info(
            f"Image search completed: {query} -> {len(images)} images "
            f"in {search_time:.0f}ms"
        )
        return result

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Google Image Search API error: {e.response.status_code} - "
            f"{e.response.text}"
        )
        return ImageSearchResponse(query=query, images=[])
    except Exception as e:
        logger.error(f"Image search failed for '{query}': {e}")
        return ImageSearchResponse(query=query, images=[])


async def search_location_images(
    location_name: str,
    city: str | None = None,
    country: str | None = None,
    num_images: int = 3,
) -> ImageSearchResponse:
    """
    Search for images of a specific location.

    Builds an optimized query including city/country context.

    Args:
        location_name: Name of the location (e.g., "Senso-ji Temple")
        city: City name for context (e.g., "Tokyo")
        country: Country name for context (e.g., "Japan")
        num_images: Number of images to return

    Returns:
        ImageSearchResponse with location images
    """
    # Build contextual query
    query_parts = [location_name]
    if city:
        query_parts.append(city)
    if country and country.lower() not in (city or "").lower():
        query_parts.append(country)

    query = " ".join(query_parts)

    return await search_images(
        query=query,
        num_images=num_images,
        image_size="large",
        image_type="photo",
    )


async def search_activity_images(
    activity_title: str,
    activity_category: str,
    location_name: str | None = None,
    num_images: int = 2,
) -> ImageSearchResponse:
    """
    Search for images related to an activity.

    Args:
        activity_title: Activity title (e.g., "Street food tour")
        activity_category: Category (e.g., "dining", "sightseeing")
        location_name: Location for context
        num_images: Number of images to return

    Returns:
        ImageSearchResponse with activity images
    """
    # Build query optimized for activity type
    query_parts = [activity_title]
    if location_name:
        query_parts.append(location_name)

    query = " ".join(query_parts)

    return await search_images(
        query=query,
        num_images=num_images,
        image_size="large",
        image_type="photo",
    )


async def search_destination_images(
    city: str,
    country: str,
    num_images: int = 5,
) -> ImageSearchResponse:
    """
    Search for images of a destination city.

    Args:
        city: City name (e.g., "Tokyo")
        country: Country name (e.g., "Japan")
        num_images: Number of images to return

    Returns:
        ImageSearchResponse with destination images
    """
    query = f"{city} {country} travel photography"

    return await search_images(
        query=query,
        num_images=num_images,
        image_size="xlarge",
        image_type="photo",
    )


async def batch_search_images(
    queries: list[str],
    num_images_per_query: int = 2,
    max_concurrent: int = 5,
) -> dict[str, ImageSearchResponse]:
    """
    Search images for multiple queries concurrently.

    Args:
        queries: List of search queries
        num_images_per_query: Number of images per query
        max_concurrent: Maximum concurrent requests

    Returns:
        Dictionary mapping query -> ImageSearchResponse
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def search_with_limit(query: str) -> tuple[str, ImageSearchResponse]:
        async with semaphore:
            result = await search_images(query, num_images_per_query)
            return query, result

    tasks = [search_with_limit(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, ImageSearchResponse] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch image search error: {result}")
            continue
        query, response = result
        output[query] = response

    return output


# MCP Tool Definition for LangGraph
IMAGE_SEARCH_TOOL_DEFINITION = {
    "name": "google_image_search",
    "description": (
        "Search for images of locations, activities, and destinations using "
        "Google Image Search. Use this to get visual references for places "
        "in the itinerary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'Senso-ji Temple Tokyo Japan')",
            },
            "num_images": {
                "type": "integer",
                "description": "Number of images to return (1-10)",
                "default": 3,
            },
            "context_type": {
                "type": "string",
                "enum": ["location", "activity", "destination"],
                "description": "Type of context for optimized search",
                "default": "location",
            },
        },
        "required": ["query"],
    },
}


async def execute_image_search_tool(
    query: str,
    num_images: int = 3,
    context_type: str = "location",
) -> dict[str, Any]:
    """
    Execute the image search tool (called by LangGraph).

    Returns dict format for LangGraph tool response.
    """
    result = await search_images(query=query, num_images=num_images)

    return {
        "query": result.query,
        "images": [
            {
                "url": img.url,
                "thumbnail_url": img.thumbnail_url,
                "width": img.width,
                "height": img.height,
                "source": img.source_domain,
                "title": img.title,
            }
            for img in result.images
        ],
        "count": len(result.images),
    }
