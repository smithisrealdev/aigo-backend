#!/usr/bin/env python3
"""
Quick test script for Google Image Search API.
Run: python scripts/test_google_image_search.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


async def test_google_image_search():
    """Test Google Custom Search Image API directly."""
    # Load settings after path setup
    from app.core.config import settings

    print("=" * 60)
    print("🔍 Testing Google Custom Search Image API")
    print("=" * 60)

    # Check config
    print(f"\n📋 Configuration:")
    api_key = settings.GOOGLE_SEARCH_API_KEY
    cx = settings.GOOGLE_SEARCH_CX
    print(f"   API Key: {'✅ Set (' + api_key[:10] + '...)' if api_key else '❌ Missing'}")
    print(f"   CX (Search Engine ID): {'✅ Set (' + cx + ')' if cx else '❌ Missing'}")
    print(f"   Enabled: {settings.GOOGLE_IMAGE_SEARCH_ENABLED}")

    if not api_key or not cx:
        print("\n❌ Error: Missing API credentials!")
        print("   Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX in .env")
        return False

    # Test queries
    test_queries = [
        "Senso-ji Temple Tokyo Japan",
        "Grand Palace Bangkok Thailand",
        "Shibuya Crossing Tokyo",
    ]

    url = "https://www.googleapis.com/customsearch/v1"
    all_success = True

    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in test_queries:
            print(f"\n🔎 Searching: '{query}'")
            print("-" * 40)

            params = {
                "key": api_key,
                "cx": cx,
                "q": query,
                "searchType": "image",
                "num": 3,
                "imgSize": "large",
                "imgType": "photo",
                "safe": "high",
            }

            try:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    print(f"   ✅ Status: {response.status_code}")
                    print(f"   📊 Results found: {len(items)}")

                    for i, item in enumerate(items, 1):
                        image_info = item.get("image", {})
                        title = item.get("title", "N/A")[:50]
                        link = item.get("link", "N/A")[:60]
                        thumb = image_info.get("thumbnailLink", "N/A")[:60]
                        width = image_info.get("width", "?")
                        height = image_info.get("height", "?")
                        source = item.get("displayLink", "N/A")

                        print(f"\n   📷 Image {i}:")
                        print(f"      Title: {title}...")
                        print(f"      URL: {link}...")
                        print(f"      Thumbnail: {thumb}...")
                        print(f"      Size: {width}x{height}")
                        print(f"      Source: {source}")

                elif response.status_code == 400:
                    print(f"   ❌ Bad Request: Check API key and CX")
                    print(f"   Response: {response.text[:200]}")
                    all_success = False

                elif response.status_code == 403:
                    print(f"   ❌ Forbidden: API key invalid or quota exceeded")
                    print(f"   Response: {response.text[:200]}")
                    all_success = False

                else:
                    print(f"   ❌ Error {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    all_success = False

            except httpx.TimeoutException:
                print(f"   ❌ Timeout: Request took too long")
                all_success = False
            except Exception as e:
                print(f"   ❌ Error: {e}")
                all_success = False

    print("\n" + "=" * 60)
    if all_success:
        print("✅ All tests passed! API is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the errors above.")
    print("=" * 60)

    return all_success


async def test_with_tool():
    """Test using the actual tool implementation."""
    print("\n" + "=" * 60)
    print("🛠️ Testing with Google Image Search Tool")
    print("=" * 60)

    from app.domains.itinerary.tools.google_image_search import (
        search_destination_images,
        search_images,
        search_location_images,
    )

    # Test 1: Basic search
    print("\n📍 Test 1: Basic search_images()")
    result = await search_images("Tokyo Tower Japan", num_images=2)
    print(f"   Query: {result.query}")
    print(f"   Images found: {len(result.images)}")
    if result.images:
        print(f"   First image: {result.images[0].url[:60]}...")

    # Test 2: Location search
    print("\n📍 Test 2: search_location_images()")
    result = await search_location_images(
        location_name="Wat Arun",
        city="Bangkok",
        country="Thailand",
        num_images=2,
    )
    print(f"   Query: {result.query}")
    print(f"   Images found: {len(result.images)}")
    if result.images:
        print(f"   First image: {result.images[0].url[:60]}...")

    # Test 3: Destination search
    print("\n📍 Test 3: search_destination_images()")
    result = await search_destination_images(
        city="Kyoto",
        country="Japan",
        num_images=3,
    )
    print(f"   Query: {result.query}")
    print(f"   Images found: {len(result.images)}")
    for i, img in enumerate(result.images, 1):
        print(f"   Image {i}: {img.source_domain} - {img.width}x{img.height}")

    print("\n✅ Tool tests completed!")


def print_quota_info():
    """Print API quota information."""
    print("\n📊 Quota Information:")
    print("   - Free tier: 100 queries/day")
    print("   - Each query with num=10 counts as 1 query")
    print("   - Check usage at: https://console.cloud.google.com/apis/dashboard")


if __name__ == "__main__":
    print("\n🚀 Starting Google Image Search API Tests\n")

    # Run direct API test
    success = asyncio.run(test_google_image_search())

    if success:
        # Run tool test if API test passed
        asyncio.run(test_with_tool())

    print_quota_info()
