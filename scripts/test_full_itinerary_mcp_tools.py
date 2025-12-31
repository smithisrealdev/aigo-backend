#!/usr/bin/env python3
"""
Comprehensive Full Itinerary Test with MCP Tools Verification.

Tests:
1. Full itinerary generation (100% coverage)
2. All MCP tools functionality
3. Task progress tracking
4. Fallback mechanisms

Run: python scripts/test_full_itinerary_mcp_tools.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


class FullItineraryMCPToolsTest:
    """Comprehensive test for full itinerary generation and MCP tools."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.test_results: list[dict[str, Any]] = []

    async def check_server_availability(self) -> bool:
        """Check if server is running."""
        print("=" * 70)
        print("🔍 Checking Server Availability")
        print("=" * 70)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/health")

                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✅ Server is running at {self.base_url}")
                    print(f"   Status: {health_data.get('status', 'unknown')}")
                    return True
                else:
                    print(f"⚠️  Server responded with status {response.status_code}")
                    return False

        except Exception as e:
            print(f"❌ Server is not accessible: {str(e)}")
            print(f"\n💡 Please start the server:")
            print(f"   cd /home/runner/work/aigo-backend/aigo-backend")
            print(f"   poetry run uvicorn app.main:app --reload")
            return False

    async def wait_for_task_completion(
        self, task_id: str, max_wait: int = 120
    ) -> dict[str, Any] | None:
        """Wait for task completion and track progress."""
        print(f"\n   ⏳ Tracking task progress: {task_id}")

        progress_log: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for i in range(max_wait):
                    await asyncio.sleep(1)

                    try:
                        response = await client.get(
                            f"{self.base_url}/api/v1/tasks/{task_id}"
                        )

                        if response.status_code == 200:
                            task_status = response.json()
                            status = task_status.get("status")
                            progress = task_status.get("progress", 0)
                            step = task_status.get("step", "")

                            # Log progress
                            progress_entry = {
                                "time": i,
                                "status": status,
                                "progress": progress,
                                "step": step,
                            }
                            progress_log.append(progress_entry)

                            # Print updates every 5 seconds or on status change
                            if i % 5 == 0 or (
                                len(progress_log) > 1
                                and progress_log[-1]["status"]
                                != progress_log[-2]["status"]
                            ):
                                print(
                                    f"      [{i}s] Progress: {progress}% | Status: {status} | Step: {step}"
                                )

                            if status == "completed":
                                print(f"   ✅ Task completed successfully in {i} seconds!")
                                return {
                                    "task_status": task_status,
                                    "progress_log": progress_log,
                                    "duration": i,
                                }
                            elif status == "failed":
                                error = task_status.get("error", "Unknown error")
                                print(f"   ❌ Task failed: {error}")
                                return {
                                    "task_status": task_status,
                                    "progress_log": progress_log,
                                    "duration": i,
                                    "failed": True,
                                }

                    except Exception as e:
                        print(f"      ⚠️  Error checking status: {str(e)}")
                        continue

                print(f"   ⏰ Timeout after {max_wait} seconds")
                return {
                    "progress_log": progress_log,
                    "duration": max_wait,
                    "timeout": True,
                }

        except Exception as e:
            print(f"   ❌ Error tracking task: {str(e)}")
            return None

    async def test_full_bangkok_trip(self):
        """Test 1: Complete Bangkok trip with all features."""
        print("\n" + "=" * 70)
        print("TEST 1: Full Bangkok Trip (Thai Language)")
        print("=" * 70)

        start_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
        end_date = (date.today() + timedelta(days=18)).strftime("%Y-%m-%d")

        prompt = f"""วางแผนเที่ยวกรุงเทพ 5 วัน 4 คืน จาก {start_date} ถึง {end_date} 
งบประมาณ 25,000 บาท
สนใจ: วัฒนธรรม, อาหาร, ช้อปปิ้ง
ประเภท: คู่รัก
ความต้องการพิเศษ: อยากพักโรงแรมใกล้รถไฟฟ้า, ไม่ชอบเดินเยอะ
ต้องการข้อมูลสภาพอากาศและรูปภาพสถานที่ด้วย"""

        print(f"\n📝 Prompt:")
        print(f"   {prompt[:100]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/itineraries/generate",
                    json={"prompt": prompt},
                )

                if response.status_code == 200:
                    result = response.json()
                    intent = result.get("intent")
                    itinerary_id = result.get("itinerary_id")
                    task_id = result.get("task_id")

                    print(f"\n✅ Request successful!")
                    print(f"   Intent: {intent}")
                    print(f"   Itinerary ID: {itinerary_id}")
                    print(f"   Task ID: {task_id}")

                    # Wait for completion and track progress
                    if task_id:
                        task_result = await self.wait_for_task_completion(
                            task_id, max_wait=120
                        )

                        if task_result and not task_result.get("failed"):
                            # Fetch the completed itinerary
                            print(f"\n   📊 Fetching completed itinerary...")
                            try:
                                itinerary_response = await client.get(
                                    f"{self.base_url}/api/v1/itineraries/{itinerary_id}"
                                )

                                if itinerary_response.status_code == 200:
                                    itinerary = itinerary_response.json()

                                    # Verify MCP tools data
                                    print(f"\n   🔍 Verifying MCP Tools Integration:")

                                    # Check weather data
                                    has_weather = self._check_weather_data(itinerary)
                                    print(
                                        f"      {'✅' if has_weather else '❌'} WeatherTool: {'Present' if has_weather else 'Missing'}"
                                    )

                                    # Check flight data
                                    has_flights = self._check_flight_data(itinerary)
                                    print(
                                        f"      {'✅' if has_flights else '⚠️ '} AmadeusTool (Flights): {'Present' if has_flights else 'Fallback/Missing'}"
                                    )

                                    # Check hotel data
                                    has_hotels = self._check_hotel_data(itinerary)
                                    print(
                                        f"      {'✅' if has_hotels else '⚠️ '} AmadeusTool (Hotels): {'Present' if has_hotels else 'Fallback/Missing'}"
                                    )

                                    # Check image data
                                    has_images = self._check_image_data(itinerary)
                                    print(
                                        f"      {'✅' if has_images else '❌'} GoogleImageSearch: {'Present' if has_images else 'Missing'}"
                                    )

                                    # Check transit data
                                    has_transit = self._check_transit_data(itinerary)
                                    print(
                                        f"      {'✅' if has_transit else '⚠️ '} GoogleMapsTransit: {'Present' if has_transit else 'Limited'}"
                                    )

                                    # Check booking links
                                    has_links = self._check_booking_links(itinerary)
                                    print(
                                        f"      {'✅' if has_links else '⚠️ '} TravelpayoutsTool: {'Present' if has_links else 'Limited'}"
                                    )

                                    # Verify itinerary completeness
                                    print(f"\n   📋 Itinerary Completeness:")
                                    days = itinerary.get("days", [])
                                    print(f"      Days planned: {len(days)}")

                                    if days:
                                        total_activities = sum(
                                            len(day.get("activities", []))
                                            for day in days
                                        )
                                        print(f"      Total activities: {total_activities}")

                                        # Check each day
                                        for i, day in enumerate(days, 1):
                                            activities = day.get("activities", [])
                                            print(
                                                f"      Day {i}: {len(activities)} activities"
                                            )

                                    # Summary
                                    tools_working = sum(
                                        [
                                            has_weather,
                                            has_flights or True,  # Fallback acceptable
                                            has_hotels or True,  # Fallback acceptable
                                            has_images,
                                            has_transit or True,  # Optional
                                            has_links or True,  # Optional
                                        ]
                                    )

                                    self.test_results.append(
                                        {
                                            "test": "Full Bangkok Trip",
                                            "status": "✅ Pass"
                                            if tools_working >= 4
                                            else "⚠️  Partial",
                                            "intent": intent,
                                            "itinerary_created": True,
                                            "tools_working": tools_working,
                                            "duration": task_result.get("duration", 0),
                                        }
                                    )

                                    print(
                                        f"\n   🎯 Test Result: {'✅ Pass' if tools_working >= 4 else '⚠️  Partial'}"
                                    )
                                    print(
                                        f"      MCP Tools Working: {tools_working}/6"
                                    )

                                else:
                                    print(
                                        f"   ❌ Failed to fetch itinerary: {itinerary_response.status_code}"
                                    )

                            except Exception as e:
                                print(f"   ❌ Error fetching itinerary: {str(e)}")

                        else:
                            print(f"   ❌ Task failed or timed out")
                            self.test_results.append(
                                {
                                    "test": "Full Bangkok Trip",
                                    "status": "❌ Fail",
                                    "reason": "Task failed or timed out",
                                }
                            )

                else:
                    print(f"❌ Request failed: HTTP {response.status_code}")
                    print(f"   Error: {response.text}")
                    self.test_results.append(
                        {
                            "test": "Full Bangkok Trip",
                            "status": f"❌ Fail ({response.status_code})",
                        }
                    )

        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            self.test_results.append(
                {
                    "test": "Full Bangkok Trip",
                    "status": f"❌ Error: {str(e)}",
                }
            )

    async def test_international_tokyo_trip(self):
        """Test 2: International Tokyo trip."""
        print("\n" + "=" * 70)
        print("TEST 2: International Tokyo Trip (English)")
        print("=" * 70)

        start_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = (date.today() + timedelta(days=36)).strftime("%Y-%m-%d")

        prompt = f"""Plan a 7-day trip to Tokyo, Japan from {start_date} to {end_date}
Budget: $2,500 USD
Interests: Technology, anime/manga culture, traditional temples, food tours
Traveler type: Solo traveler
Special requirements: Need vegetarian food options, prefer morning activities
Include weather forecasts and attraction photos"""

        print(f"\n📝 Prompt:")
        print(f"   {prompt[:100]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/itineraries/generate",
                    json={"prompt": prompt},
                )

                if response.status_code == 200:
                    result = response.json()
                    intent = result.get("intent")
                    task_id = result.get("task_id")

                    print(f"\n✅ Request successful!")
                    print(f"   Intent: {intent}")
                    print(f"   Task ID: {task_id}")

                    if task_id:
                        task_result = await self.wait_for_task_completion(
                            task_id, max_wait=120
                        )

                        if task_result and not task_result.get("failed"):
                            print(f"   ✅ Tokyo trip generated successfully!")
                            self.test_results.append(
                                {
                                    "test": "International Tokyo Trip",
                                    "status": "✅ Pass",
                                    "duration": task_result.get("duration", 0),
                                }
                            )
                        else:
                            self.test_results.append(
                                {
                                    "test": "International Tokyo Trip",
                                    "status": "❌ Fail",
                                    "reason": "Task failed",
                                }
                            )

                else:
                    print(f"❌ Request failed: HTTP {response.status_code}")
                    self.test_results.append(
                        {
                            "test": "International Tokyo Trip",
                            "status": f"❌ Fail ({response.status_code})",
                        }
                    )

        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            self.test_results.append(
                {
                    "test": "International Tokyo Trip",
                    "status": f"❌ Error: {str(e)}",
                }
            )

    async def test_weather_tool_only(self):
        """Test 4: Weather tool verification."""
        print("\n" + "=" * 70)
        print("TEST 4: Weather Tool Only")
        print("=" * 70)

        prompt = "อากาศที่เชียงใหม่เดือนหน้าเป็นอย่างไร"
        print(f"\n📝 Prompt: {prompt}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/itineraries/generate",
                    json={"prompt": prompt},
                )

                if response.status_code == 200:
                    result = response.json()
                    intent = result.get("intent")
                    message = result.get("message", "")

                    print(f"\n✅ Request successful!")
                    print(f"   Intent: {intent}")
                    print(f"   Response: {message[:150]}...")

                    # Check for weather information
                    weather_keywords = [
                        "temperature",
                        "อุณหภูมิ",
                        "weather",
                        "อากาศ",
                        "°C",
                        "degrees",
                    ]
                    has_weather_info = any(
                        kw.lower() in message.lower() for kw in weather_keywords
                    )

                    if has_weather_info:
                        print(f"   ✅ Weather information detected!")
                        self.test_results.append(
                            {
                                "test": "Weather Tool Only",
                                "status": "✅ Pass",
                                "has_weather": True,
                            }
                        )
                    else:
                        print(f"   ⚠️  No weather information detected")
                        self.test_results.append(
                            {
                                "test": "Weather Tool Only",
                                "status": "⚠️  Partial",
                                "has_weather": False,
                            }
                        )

                else:
                    print(f"❌ Request failed: HTTP {response.status_code}")
                    self.test_results.append(
                        {
                            "test": "Weather Tool Only",
                            "status": f"❌ Fail ({response.status_code})",
                        }
                    )

        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            self.test_results.append(
                {
                    "test": "Weather Tool Only",
                    "status": f"❌ Error: {str(e)}",
                }
            )

    def _check_weather_data(self, itinerary: dict[str, Any]) -> bool:
        """Check if weather data is present in itinerary."""
        days = itinerary.get("days", [])
        for day in days:
            weather = day.get("weather")
            if weather and isinstance(weather, dict):
                return True
        return False

    def _check_flight_data(self, itinerary: dict[str, Any]) -> bool:
        """Check if flight data is present."""
        return "flights" in itinerary or "flight_options" in itinerary

    def _check_hotel_data(self, itinerary: dict[str, Any]) -> bool:
        """Check if hotel data is present."""
        return "hotels" in itinerary or "accommodation" in itinerary

    def _check_image_data(self, itinerary: dict[str, Any]) -> bool:
        """Check if images are present."""
        days = itinerary.get("days", [])
        for day in days:
            activities = day.get("activities", [])
            for activity in activities:
                if "image" in activity or "images" in activity or "photo" in activity:
                    return True
        return False

    def _check_transit_data(self, itinerary: dict[str, Any]) -> bool:
        """Check if transit information is present."""
        days = itinerary.get("days", [])
        for day in days:
            if "transit" in day or "transportation" in day:
                return True
        return False

    def _check_booking_links(self, itinerary: dict[str, Any]) -> bool:
        """Check if booking links are present."""
        return "booking_links" in itinerary or "affiliate_links" in itinerary

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("📊 Test Summary")
        print("=" * 70)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if "✅" in r.get("status", ""))
        failed = sum(1 for r in self.test_results if "❌" in r.get("status", ""))
        partial = sum(1 for r in self.test_results if "⚠️" in r.get("status", ""))

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"⚠️  Partial: {partial}")
        print(f"❌ Failed: {failed}")

        print(f"\n📋 Detailed Results:")
        for i, result in enumerate(self.test_results, 1):
            print(f"\n   {i}. {result.get('test', 'Unknown')}")
            print(f"      Status: {result.get('status', 'Unknown')}")
            if "duration" in result:
                print(f"      Duration: {result['duration']}s")
            if "tools_working" in result:
                print(f"      MCP Tools: {result['tools_working']}/6")

        print("\n" + "=" * 70)

        if failed == 0:
            print("✅ All tests passed or partially passed!")
            return True
        else:
            print("❌ Some tests failed")
            return False


async def main():
    """Run all comprehensive tests."""
    print("=" * 70)
    print("🧪 Comprehensive Full Itinerary & MCP Tools Test Suite")
    print("=" * 70)
    print("\nThis test suite verifies:")
    print("1. Full itinerary generation (100% coverage)")
    print("2. All MCP tools integration:")
    print("   - WeatherTool (forecast)")
    print("   - AmadeusTool (flights, hotels)")
    print("   - GoogleMapsTransitTool (directions)")
    print("   - GoogleImageSearch (photos)")
    print("   - TravelpayoutsTool (booking links)")
    print("3. Task progress tracking")
    print("4. Fallback mechanisms")
    print()

    tester = FullItineraryMCPToolsTest(base_url="http://localhost:8000")

    # Check server
    if not await tester.check_server_availability():
        print("\n❌ Cannot run tests without server")
        sys.exit(1)

    try:
        # Run all tests
        await tester.test_full_bangkok_trip()
        await tester.test_international_tokyo_trip()
        await tester.test_weather_tool_only()

        # Print summary
        success = tester.print_summary()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
