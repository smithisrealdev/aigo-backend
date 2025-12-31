#!/usr/bin/env python3
"""
Integration test for /api/v1/itineraries/generate endpoint with Weather API.

Tests various weather-related scenarios:
1. Asking about weather conditions
2. Weather forecasts for re-planning
3. Weather integration in itinerary creation

Run: python scripts/test_itinerary_generate_weather.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


class ItineraryGenerateWeatherTest:
    """Integration test for weather-related itinerary generation."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.results = []

    async def test_weather_inquiry(self):
        """Test Case 1: Ask about weather conditions."""
        print("\n" + "=" * 70)
        print("TEST 1: Weather Inquiry (General Question)")
        print("=" * 70)

        test_cases = [
            {
                "name": "Current weather question (Thai)",
                "prompt": "อากาศที่กรุงเทพตอนนี้เป็นอย่างไรบ้าง",
                "expected_intent": "general_inquiry",
            },
            {
                "name": "Weather forecast question (English)",
                "prompt": "What's the weather like in Tokyo in April?",
                "expected_intent": "general_inquiry",
            },
            {
                "name": "Weather with trip planning (Thai)",
                "prompt": "อากาศที่โตเกียวช่วงเดือนเมษายนเป็นยังไง ควรไปเที่ยวไหม",
                "expected_intent": "general_inquiry or decision_support",
            },
        ]

        for i, test in enumerate(test_cases, 1):
            print(f"\n🧪 Test {i}: {test['name']}")
            print(f"   Prompt: {test['prompt']}")

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/itineraries/generate",
                        json={"prompt": test["prompt"]},
                    )

                    if response.status_code == 200:
                        result = response.json()
                        intent = result.get("intent")
                        message = result.get("message", "")

                        print(f"   ✅ Success!")
                        print(f"   Intent: {intent}")
                        print(f"   Message: {message[:100]}...")

                        # Check if weather info is in response
                        weather_keywords = ["weather", "อากาศ", "temperature", "อุณหภูมิ", "rain", "ฝน"]
                        has_weather = any(kw.lower() in message.lower() for kw in weather_keywords)

                        if has_weather:
                            print(f"   🌤️  Weather info detected in response")
                        else:
                            print(f"   ⚠️  No weather info detected")

                        self.results.append({
                            "test": test["name"],
                            "status": "✅ Pass",
                            "intent": intent,
                            "has_weather": has_weather,
                        })
                    else:
                        print(f"   ❌ Failed: HTTP {response.status_code}")
                        print(f"   Error: {response.text}")
                        self.results.append({
                            "test": test["name"],
                            "status": f"❌ Fail ({response.status_code})",
                        })

            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                self.results.append({
                    "test": test["name"],
                    "status": f"❌ Error: {str(e)}",
                })

    async def test_weather_for_replan(self):
        """Test Case 2: Weather forecast for re-planning."""
        print("\n" + "=" * 70)
        print("TEST 2: Weather Forecast for Re-planning")
        print("=" * 70)

        test_cases = [
            {
                "name": "Check weather before finalizing plan",
                "prompt": "ฉันกำลังจะไปกรุงเทพสัปดาห์หน้า ช่วยดูสภาพอากาศให้หน่อย แล้วแนะนำว่าควรไปไหนดี",
                "expected_intent": "general_inquiry or decision_support",
            },
            {
                "name": "Weather-based activity suggestion",
                "prompt": "ถ้าฝนตกที่เชียงใหม่ ควรทำอะไรดี",
                "expected_intent": "decision_support",
            },
            {
                "name": "Adjust plan based on weather",
                "prompt": "I'm going to Phuket next week. If it rains, what indoor activities can I do?",
                "expected_intent": "decision_support",
            },
        ]

        for i, test in enumerate(test_cases, 1):
            print(f"\n🧪 Test {i}: {test['name']}")
            print(f"   Prompt: {test['prompt']}")

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/itineraries/generate",
                        json={"prompt": test["prompt"]},
                    )

                    if response.status_code == 200:
                        result = response.json()
                        intent = result.get("intent")
                        message = result.get("message", "")
                        suggestions = result.get("suggestions", [])

                        print(f"   ✅ Success!")
                        print(f"   Intent: {intent}")
                        print(f"   Message: {message[:100]}...")

                        if suggestions:
                            print(f"   💡 Suggestions: {len(suggestions)} items")
                            for sugg in suggestions[:3]:
                                print(f"      - {sugg}")

                        self.results.append({
                            "test": test["name"],
                            "status": "✅ Pass",
                            "intent": intent,
                            "has_suggestions": len(suggestions) > 0,
                        })
                    else:
                        print(f"   ❌ Failed: HTTP {response.status_code}")
                        self.results.append({
                            "test": test["name"],
                            "status": f"❌ Fail ({response.status_code})",
                        })

            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                self.results.append({
                    "test": test["name"],
                    "status": f"❌ Error: {str(e)}",
                })

    async def test_weather_in_itinerary_creation(self):
        """Test Case 3: Weather integration in itinerary creation."""
        print("\n" + "=" * 70)
        print("TEST 3: Weather Integration in Itinerary Creation")
        print("=" * 70)

        start_date = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (date.today() + timedelta(days=12)).strftime("%Y-%m-%d")

        test_cases = [
            {
                "name": "Trip planning with weather consideration (Thai)",
                "prompt": f"วางแผนเที่ยวกรุงเทพ 5 วัน จาก {start_date} ถึง {end_date} งบ 20000 บาท อยากทราบสภาพอากาศด้วย",
                "expected_intent": "trip_generation",
            },
            {
                "name": "Beach trip with weather check",
                "prompt": f"Plan a beach vacation to Phuket from {start_date} to {end_date}, budget $1000. Consider weather conditions.",
                "expected_intent": "trip_generation",
            },
            {
                "name": "Mountain trip with weather awareness",
                "prompt": f"เที่ยวเชียงใหม่ 3 วัน งบ 15000 อยากขึ้นดอย ต้องดูสภาพอากาศด้วยนะ",
                "expected_intent": "trip_generation",
            },
        ]

        for i, test in enumerate(test_cases, 1):
            print(f"\n🧪 Test {i}: {test['name']}")
            print(f"   Prompt: {test['prompt']}")

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/itineraries/generate",
                        json={"prompt": test["prompt"]},
                    )

                    if response.status_code == 200:
                        result = response.json()
                        intent = result.get("intent")

                        print(f"   ✅ Success!")
                        print(f"   Intent: {intent}")

                        if intent == "trip_generation":
                            itinerary_id = result.get("itinerary_id")
                            task_id = result.get("task_id")
                            status_val = result.get("status")
                            websocket_url = result.get("websocket_url")

                            print(f"   🎯 Itinerary ID: {itinerary_id}")
                            print(f"   📋 Task ID: {task_id}")
                            print(f"   ⏳ Status: {status_val}")
                            print(f"   🔌 WebSocket: {websocket_url}")

                            # Wait a bit and check task status
                            await asyncio.sleep(3)

                            try:
                                status_response = await client.get(
                                    f"{self.base_url}/api/v1/tasks/{task_id}"
                                )

                                if status_response.status_code == 200:
                                    task_status = status_response.json()
                                    task_state = task_status.get("status")
                                    progress = task_status.get("progress", 0)

                                    print(f"   📊 Task Status: {task_state}")
                                    print(f"   📈 Progress: {progress}%")

                                    # Check if weather data is being gathered
                                    current_step = task_status.get("current_step", "")
                                    if "weather" in current_step.lower():
                                        print(f"   🌤️  Weather step detected: {current_step}")

                            except Exception as e:
                                print(f"   ⚠️  Could not check task status: {str(e)}")

                            self.results.append({
                                "test": test["name"],
                                "status": "✅ Pass",
                                "intent": intent,
                                "itinerary_created": itinerary_id is not None,
                                "task_created": task_id is not None,
                            })
                        else:
                            print(f"   ⚠️  Unexpected intent: {intent}")
                            self.results.append({
                                "test": test["name"],
                                "status": f"⚠️  Unexpected intent: {intent}",
                            })
                    else:
                        print(f"   ❌ Failed: HTTP {response.status_code}")
                        print(f"   Error: {response.text}")
                        self.results.append({
                            "test": test["name"],
                            "status": f"❌ Fail ({response.status_code})",
                        })

            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                self.results.append({
                    "test": test["name"],
                    "status": f"❌ Error: {str(e)}",
                })

    async def check_server_availability(self):
        """Check if the server is running."""
        print("=" * 70)
        print("🔍 Checking Server Availability")
        print("=" * 70)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/health")

                if response.status_code == 200:
                    print(f"✅ Server is running at {self.base_url}")
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

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("📊 Test Summary")
        print("=" * 70)

        passed = sum(1 for r in self.results if "✅" in r.get("status", ""))
        failed = sum(1 for r in self.results if "❌" in r.get("status", ""))
        warnings = sum(1 for r in self.results if "⚠️" in r.get("status", ""))

        print(f"\nTotal Tests: {len(self.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")

        print(f"\n📋 Detailed Results:")
        for i, result in enumerate(self.results, 1):
            test_name = result.get("test", "Unknown")
            status = result.get("status", "Unknown")
            print(f"   {i}. {test_name}")
            print(f"      Status: {status}")

            if "intent" in result:
                print(f"      Intent: {result['intent']}")
            if "has_weather" in result:
                print(f"      Weather Info: {'Yes' if result['has_weather'] else 'No'}")
            if "itinerary_created" in result:
                print(f"      Itinerary: {'Created' if result['itinerary_created'] else 'Not Created'}")

        print("\n" + "=" * 70)

        if failed == 0 and warnings == 0:
            print("✅ All tests passed!")
            return True
        elif failed == 0:
            print("⚠️  Tests completed with warnings")
            return True
        else:
            print("❌ Some tests failed")
            return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("🌤️  Weather API Integration Test for /api/v1/itineraries/generate")
    print("=" * 70)

    # Configuration
    base_url = "http://localhost:8000"

    tester = ItineraryGenerateWeatherTest(base_url=base_url)

    # Check if server is available
    server_available = await tester.check_server_availability()

    if not server_available:
        print("\n" + "=" * 70)
        print("⚠️  Server Not Available - Cannot Run Tests")
        print("=" * 70)
        print("\n📚 Test Cases Documented:")
        print("\n1. Weather Inquiry:")
        print("   - Current weather questions")
        print("   - Weather forecast questions")
        print("   - Weather with trip planning")
        print("\n2. Weather for Re-planning:")
        print("   - Check weather before finalizing")
        print("   - Weather-based activity suggestions")
        print("   - Adjust plan based on weather")
        print("\n3. Weather in Itinerary Creation:")
        print("   - Trip planning with weather consideration")
        print("   - Beach trip with weather check")
        print("   - Mountain trip with weather awareness")
        print("\n" + "=" * 70)
        sys.exit(1)

    # Run tests
    try:
        await tester.test_weather_inquiry()
        await tester.test_weather_for_replan()
        await tester.test_weather_in_itinerary_creation()

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
