"""
Tests for Google Image Search MCP tool.

Tests image search functionality for locations, activities, and destinations.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.domains.itinerary.tools.google_image_search import (
    search_images,
    search_location_images,
    search_destination_images,
    search_activity_images,
    batch_search_images,
    execute_image_search_tool,
    ImageSearchResponse,
    ImageSearchResult,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _image_cache,
)


class TestImageSearchResult:
    """Tests for ImageSearchResult schema."""

    def test_image_search_result_minimal(self):
        """Test creating ImageSearchResult with minimal data."""
        result = ImageSearchResult(
            url="https://example.com/image.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        )
        assert result.url == "https://example.com/image.jpg"
        assert result.thumbnail_url == "https://example.com/thumb.jpg"
        assert result.width is None
        assert result.height is None

    def test_image_search_result_full(self):
        """Test creating ImageSearchResult with all fields."""
        result = ImageSearchResult(
            url="https://example.com/image.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
            width=1920,
            height=1080,
            source_url="https://example.com/page",
            source_domain="example.com",
            title="Test Image",
        )
        assert result.width == 1920
        assert result.height == 1080
        assert result.source_domain == "example.com"


class TestImageSearchResponse:
    """Tests for ImageSearchResponse schema."""

    def test_image_search_response_empty(self):
        """Test creating empty ImageSearchResponse."""
        response = ImageSearchResponse(
            query="test query",
            images=[],
        )
        assert response.query == "test query"
        assert len(response.images) == 0
        assert response.total_results is None

    def test_image_search_response_with_images(self):
        """Test creating ImageSearchResponse with images."""
        images = [
            ImageSearchResult(
                url="https://example.com/1.jpg",
                thumbnail_url="https://example.com/1_thumb.jpg",
            ),
            ImageSearchResult(
                url="https://example.com/2.jpg",
                thumbnail_url="https://example.com/2_thumb.jpg",
            ),
        ]
        response = ImageSearchResponse(
            query="Tokyo",
            images=images,
            total_results=100,
            search_time_ms=150.5,
        )
        assert len(response.images) == 2
        assert response.total_results == 100
        assert response.search_time_ms == 150.5


class TestCaching:
    """Tests for caching functionality."""

    def test_cache_key_generation(self):
        """Test cache key generation."""
        key1 = _get_cache_key("Tokyo", 5)
        key2 = _get_cache_key("Tokyo", 5)
        key3 = _get_cache_key("Tokyo", 3)
        key4 = _get_cache_key("Osaka", 5)

        assert key1 == key2  # Same query and num should produce same key
        assert key1 != key3  # Different num should produce different key
        assert key1 != key4  # Different query should produce different key

    def test_set_and_get_cached_result(self):
        """Test setting and getting cached results."""
        # Clear cache first
        _image_cache.clear()

        test_response = ImageSearchResponse(
            query="test",
            images=[
                ImageSearchResult(
                    url="https://example.com/image.jpg",
                    thumbnail_url="https://example.com/thumb.jpg",
                )
            ],
        )

        cache_key = "test_key"
        _set_cached_result(cache_key, test_response)

        cached = _get_cached_result(cache_key)
        assert cached is not None
        assert cached.query == "test"
        assert len(cached.images) == 1

    def test_cache_miss(self):
        """Test cache miss returns None."""
        _image_cache.clear()
        result = _get_cached_result("nonexistent_key")
        assert result is None


class TestSearchImages:
    """Tests for search_images function."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for tests."""
        with patch("app.domains.itinerary.tools.google_image_search.settings") as mock:
            mock.GOOGLE_IMAGE_SEARCH_ENABLED = True
            mock.GOOGLE_SEARCH_API_KEY = "test_api_key"
            mock.GOOGLE_SEARCH_CX = "test_cx"
            mock.GOOGLE_IMAGE_CACHE_TTL = 86400
            yield mock

    @pytest.fixture
    def mock_api_response(self):
        """Mock API response."""
        return {
            "searchInformation": {"totalResults": "100"},
            "items": [
                {
                    "link": "https://example.com/image1.jpg",
                    "displayLink": "example.com",
                    "title": "Test Image 1",
                    "image": {
                        "thumbnailLink": "https://example.com/thumb1.jpg",
                        "width": 1920,
                        "height": 1080,
                        "contextLink": "https://example.com/page1",
                    },
                },
                {
                    "link": "https://example.com/image2.jpg",
                    "displayLink": "example2.com",
                    "title": "Test Image 2",
                    "image": {
                        "thumbnailLink": "https://example.com/thumb2.jpg",
                        "width": 1600,
                        "height": 900,
                        "contextLink": "https://example.com/page2",
                    },
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_search_images_disabled(self):
        """Test search returns empty when disabled."""
        with patch("app.domains.itinerary.tools.google_image_search.settings") as mock:
            mock.GOOGLE_IMAGE_SEARCH_ENABLED = False
            mock.GOOGLE_SEARCH_API_KEY = ""
            mock.GOOGLE_SEARCH_CX = ""

            result = await search_images("Tokyo")

            assert result.query == "Tokyo"
            assert len(result.images) == 0

    @pytest.mark.asyncio
    async def test_search_images_no_credentials(self):
        """Test search returns empty when no credentials."""
        with patch("app.domains.itinerary.tools.google_image_search.settings") as mock:
            mock.GOOGLE_IMAGE_SEARCH_ENABLED = True
            mock.GOOGLE_SEARCH_API_KEY = ""
            mock.GOOGLE_SEARCH_CX = ""

            result = await search_images("Tokyo")

            assert result.query == "Tokyo"
            assert len(result.images) == 0

    @pytest.mark.asyncio
    async def test_search_images_success(self, mock_settings, mock_api_response):
        """Test successful image search."""
        _image_cache.clear()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await search_images("Tokyo", num_images=2)

            assert result.query == "Tokyo"
            assert len(result.images) == 2
            assert result.images[0].url == "https://example.com/image1.jpg"
            assert result.images[0].width == 1920
            assert result.total_results == 100

    @pytest.mark.asyncio
    async def test_search_images_api_error(self, mock_settings):
        """Test search handles API errors gracefully."""
        _image_cache.clear()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=Exception("API Error")
            )
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await search_images("Tokyo")

            assert result.query == "Tokyo"
            assert len(result.images) == 0


class TestSearchLocationImages:
    """Tests for search_location_images function."""

    @pytest.mark.asyncio
    async def test_search_location_images_query_building(self):
        """Test that location images builds correct query."""
        with patch(
            "app.domains.itinerary.tools.google_image_search.search_images"
        ) as mock_search:
            mock_search.return_value = ImageSearchResponse(
                query="test", images=[]
            )

            await search_location_images(
                location_name="Senso-ji Temple",
                city="Tokyo",
                country="Japan",
                num_images=3,
            )

            # Check that search_images was called with correct query
            mock_search.assert_called_once()
            call_args = mock_search.call_args
            assert "Senso-ji Temple" in call_args.kwargs["query"]
            assert "Tokyo" in call_args.kwargs["query"]
            assert call_args.kwargs["num_images"] == 3


class TestSearchDestinationImages:
    """Tests for search_destination_images function."""

    @pytest.mark.asyncio
    async def test_search_destination_images_query(self):
        """Test destination images builds correct query."""
        with patch(
            "app.domains.itinerary.tools.google_image_search.search_images"
        ) as mock_search:
            mock_search.return_value = ImageSearchResponse(
                query="test", images=[]
            )

            await search_destination_images(
                city="Tokyo",
                country="Japan",
                num_images=5,
            )

            mock_search.assert_called_once()
            call_args = mock_search.call_args
            assert "Tokyo" in call_args.kwargs["query"]
            assert "Japan" in call_args.kwargs["query"]
            assert "travel photography" in call_args.kwargs["query"]


class TestSearchActivityImages:
    """Tests for search_activity_images function."""

    @pytest.mark.asyncio
    async def test_search_activity_images_query(self):
        """Test activity images builds correct query."""
        with patch(
            "app.domains.itinerary.tools.google_image_search.search_images"
        ) as mock_search:
            mock_search.return_value = ImageSearchResponse(
                query="test", images=[]
            )

            await search_activity_images(
                activity_title="Street food tour",
                activity_category="dining",
                location_name="Bangkok",
                num_images=2,
            )

            mock_search.assert_called_once()
            call_args = mock_search.call_args
            assert "Street food tour" in call_args.kwargs["query"]
            assert "Bangkok" in call_args.kwargs["query"]


class TestBatchSearchImages:
    """Tests for batch_search_images function."""

    @pytest.mark.asyncio
    async def test_batch_search_images(self):
        """Test batch search for multiple queries."""
        with patch(
            "app.domains.itinerary.tools.google_image_search.search_images"
        ) as mock_search:
            mock_search.return_value = ImageSearchResponse(
                query="test",
                images=[
                    ImageSearchResult(
                        url="https://example.com/image.jpg",
                        thumbnail_url="https://example.com/thumb.jpg",
                    )
                ],
            )

            queries = ["Tokyo Tower", "Senso-ji Temple", "Shibuya Crossing"]
            results = await batch_search_images(
                queries=queries, num_images_per_query=2, max_concurrent=5
            )

            assert len(results) == 3
            for query in queries:
                assert query in results


class TestExecuteImageSearchTool:
    """Tests for execute_image_search_tool function."""

    @pytest.mark.asyncio
    async def test_execute_tool_returns_dict(self):
        """Test that execute_image_search_tool returns correct format."""
        with patch(
            "app.domains.itinerary.tools.google_image_search.search_images"
        ) as mock_search:
            mock_search.return_value = ImageSearchResponse(
                query="Tokyo",
                images=[
                    ImageSearchResult(
                        url="https://example.com/image.jpg",
                        thumbnail_url="https://example.com/thumb.jpg",
                        width=1920,
                        height=1080,
                        source_domain="example.com",
                        title="Tokyo Image",
                    )
                ],
            )

            result = await execute_image_search_tool(
                query="Tokyo", num_images=3, context_type="location"
            )

            assert result["query"] == "Tokyo"
            assert result["count"] == 1
            assert len(result["images"]) == 1
            assert result["images"][0]["url"] == "https://example.com/image.jpg"
            assert result["images"][0]["width"] == 1920
