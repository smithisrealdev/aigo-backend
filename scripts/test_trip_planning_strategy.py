#!/usr/bin/env python3
"""
Trip Planning Strategy Test - Focused MCP Tools Integration Validation

This test specifically validates:
1. Trip generation request success
2. MCP tools integration status
3. Itinerary completeness
4. Tool availability and functionality

Based on analysis of Bangkok trip test results showing tool integration issues.

Run: python scripts/test_trip_planning_strategy.py
"""

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Optional: WebSocket support (install with: pip install websockets)
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("⚠️  Note: 'websockets' library not installed. WebSocket tests will be skipped.")
    print("   Install with: pip install websockets")


# Test Configuration Constants
MAX_TASK_WAIT_SECONDS = 120
TASK_STATUS_POLL_INTERVAL = 1
STATUS_PRINT_INTERVAL = 10

# Completeness Scoring Weights
SCORE_DAILY_PLANS = 25
SCORE_ALL_DAYS_PLANNED = 25
SCORE_HAS_ACTIVITIES = 25
SCORE_HAS_WEATHER = 15
SCORE_HAS_BUDGET = 10

# Default Test Prompt
DEFAULT_TEST_PROMPT = """วางแผนเที่ยวกรุงเทพ 5 วัน 4 คืน จาก {start_date} ถึง {end_date}
งบประมาณ 25,000 บาท
สนใจ: วัฒนธรรม, อาหาร, ช้อปปิ้ง
ประเภท: คู่รัก
ต้องการข้อมูลสภาพอากาศและรูปภาพสถานที่ด้วย"""


class TripPlanningStrategyTest:
    """Strategy test for trip planning feature with MCP tools validation."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.ws_base_url = base_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
        self.test_results: dict[str, Any] = {
            "server_available": False,
            "request_success": False,
            "task_completion": False,
            "websocket_tested": False,
            "websocket_working": False,
            "context_retention_tested": False,
            "context_fully_retained": False,
            "mcp_tools_status": {},
            "itinerary_completeness": {},
            "overall_pass": False,
        }
        self.conversation_history: list[dict[str, Any]] = []

    async def check_server_availability(self) -> bool:
        """Check if server is running."""
        print("=" * 80)
        print("🔍 STEP 1: Checking Server Availability")
        print("=" * 80)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/health")

                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✅ Server is running at {self.base_url}")
                    print(f"   Status: {health_data.get('status', 'unknown')}")
                    self.test_results["server_available"] = True
                    return True
                else:
                    print(f"❌ Server responded with status {response.status_code}")
                    return False

        except Exception as e:
            print(f"❌ Server is not accessible: {str(e)}")
            print(f"\n💡 Please start the server:")
            print(f"   poetry run uvicorn app.main:app --reload")
            return False

    async def test_trip_generation_request(
        self, custom_prompt: str | None = None
    ) -> dict[str, Any] | None:
        """Test trip generation request and capture response."""
        print("\n" + "=" * 80)
        print("🧪 STEP 2: Testing Trip Generation Request")
        print("=" * 80)

        # Use custom prompt or default Bangkok trip
        if custom_prompt:
            prompt = custom_prompt
        else:
            start_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
            end_date = (date.today() + timedelta(days=18)).strftime("%Y-%m-%d")
            prompt = DEFAULT_TEST_PROMPT.format(
                start_date=start_date, end_date=end_date
            )

        print(f"\n📝 Test Prompt:")
        # Use proper newline instead of chr(10)
        print(f"   {prompt.replace('\n', '\n   ')}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/chat",
                    json={"message": prompt},
                )

                print(f"\n📊 Response Status: {response.status_code}")

                if response.status_code == 200:
                    response_data = response.json()
                    print(f"✅ Request successful!")
                    print(f"\n📄 Response Data:")
                    print(f"   Intent: {response_data.get('intent', 'N/A')}")

                    # Check for itinerary_id and task_id
                    if "itinerary_id" in response_data:
                        print(f"   Itinerary ID: {response_data['itinerary_id']}")
                    if "task_id" in response_data:
                        print(f"   Task ID: {response_data['task_id']}")

                    self.test_results["request_success"] = True
                    return response_data
                else:
                    print(f"❌ Request failed with status {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None

        except Exception as e:
            print(f"❌ Error during request: {str(e)}")
            return None

    async def track_progress_via_websocket(
        self, task_id: str, timeout: int = MAX_TASK_WAIT_SECONDS
    ) -> dict[str, Any]:
        """Track task progress via WebSocket connection."""
        print("\n" + "=" * 80)
        print("🌐 STEP 3a: Testing WebSocket Progress Tracking")
        print("=" * 80)

        ws_result = {
            "connected": False,
            "messages_received": 0,
            "final_status": None,
            "progress_updates": [],
            "error": None,
        }

        if not WEBSOCKETS_AVAILABLE:
            print("⚠️  WebSocket library not available - skipping WebSocket test")
            print("   Install with: pip install websockets")
            self.test_results["websocket_tested"] = False
            self.test_results["websocket_working"] = False
            ws_result["error"] = "websockets library not installed"
            return ws_result

        ws_url = f"{self.ws_base_url}/api/v1/ws/itinerary/{task_id}"
        print(f"\n🔌 Connecting to WebSocket: {ws_url}")

        try:
            async with websockets.connect(ws_url, ping_interval=20) as websocket:
                ws_result["connected"] = True
                print("✅ WebSocket connected successfully")
                
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    # Check timeout
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > timeout:
                        print(f"\n⏰ WebSocket timeout after {timeout} seconds")
                        break
                    
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(
                            websocket.recv(), timeout=5.0
                        )
                        
                        data = json.loads(message)
                        ws_result["messages_received"] += 1
                        
                        # Extract progress info
                        progress = data.get("progress", 0)
                        status = data.get("status", "unknown")
                        step = data.get("step", "")
                        message_text = data.get("message", "")
                        
                        ws_result["progress_updates"].append({
                            "progress": progress,
                            "status": status,
                            "step": step,
                            "message": message_text,
                        })
                        
                        # Print progress update
                        print(f"   📊 [{progress}%] {status} - {step}: {message_text}")
                        
                        # Check if completed or failed
                        if status in ["completed", "failed"]:
                            ws_result["final_status"] = status
                            print(f"\n{'✅' if status == 'completed' else '❌'} Task {status}")
                            break
                            
                    except asyncio.TimeoutError:
                        # No message received in 5 seconds, check if still connected
                        continue
                    except Exception as e:
                        print(f"⚠️  Error receiving message: {str(e)}")
                        break
                
                self.test_results["websocket_tested"] = True
                self.test_results["websocket_working"] = ws_result["connected"] and ws_result["messages_received"] > 0
                
                return ws_result
                
        except Exception as e:
            print(f"❌ WebSocket connection failed: {str(e)}")
            print(f"   This is acceptable if WebSocket endpoint is not configured")
            ws_result["error"] = str(e)
            self.test_results["websocket_tested"] = True
            self.test_results["websocket_working"] = False
            return ws_result

    async def test_context_retention(self) -> dict[str, Any]:
        """Test multi-turn conversation context retention."""
        print("\n" + "=" * 80)
        print("🧠 STEP 4: Testing Context Retention")
        print("=" * 80)

        context_result = {
            "turns_completed": 0,
            "context_preserved": False,
            "final_itinerary_includes_context": False,
            "conversation_flow": [],
        }

        print("\n📝 Starting multi-turn conversation test...")

        # Turn 1: Initial vague request
        print("\n   Turn 1: Vague request")
        turn1_prompt = "อยากไปเที่ยวทะเล อากาศดีๆ"
        print(f"   User: {turn1_prompt}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response1 = await client.post(
                    f"{self.base_url}/api/v1/chat",
                    json={"message": turn1_prompt},
                )

                if response1.status_code == 200:
                    result1 = response1.json()
                    print(f"   AI: {result1.get('response', 'N/A')[:100]}...")
                    context_result["turns_completed"] = 1
                    context_result["conversation_flow"].append({
                        "turn": 1,
                        "user_input": turn1_prompt,
                        "ai_response": result1.get("response", ""),
                        "intent": result1.get("intent", ""),
                    })
                    
                    # Store conversation_id if available
                    conversation_id = result1.get("conversation_id")
                    
                    # Turn 2: Add more details (should retain context)
                    print("\n   Turn 2: Adding details (testing context)")
                    turn2_prompt = "งบ 20,000 บาท ไป 3 วัน อยากไปภูเก็ต"
                    print(f"   User: {turn2_prompt}")

                    payload2 = {"message": turn2_prompt}
                    if conversation_id:
                        payload2["conversation_id"] = conversation_id

                    response2 = await client.post(
                        f"{self.base_url}/api/v1/chat",
                        json=payload2,
                    )

                    if response2.status_code == 200:
                        result2 = response2.json()
                        print(f"   AI: {result2.get('response', 'N/A')[:100]}...")
                        context_result["turns_completed"] = 2
                        context_result["conversation_flow"].append({
                            "turn": 2,
                            "user_input": turn2_prompt,
                            "ai_response": result2.get("response", ""),
                            "intent": result2.get("intent", ""),
                        })
                        
                        # Turn 3: Confirm and generate (should use all context)
                        print("\n   Turn 3: Confirming dates (should generate itinerary)")
                        start_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
                        end_date = (date.today() + timedelta(days=16)).strftime("%Y-%m-%d")
                        turn3_prompt = f"ไปวันที่ {start_date} ถึง {end_date}"
                        print(f"   User: {turn3_prompt}")

                        payload3 = {"message": turn3_prompt}
                        if conversation_id:
                            payload3["conversation_id"] = conversation_id

                        response3 = await client.post(
                            f"{self.base_url}/api/v1/chat",
                            json=payload3,
                        )

                        if response3.status_code == 200:
                            result3 = response3.json()
                            context_result["turns_completed"] = 3
                            context_result["conversation_flow"].append({
                                "turn": 3,
                                "user_input": turn3_prompt,
                                "ai_response": result3.get("response", ""),
                                "intent": result3.get("intent", ""),
                                "itinerary_id": result3.get("itinerary_id"),
                                "task_id": result3.get("task_id"),
                            })
                            
                            # Check if itinerary was generated with all context
                            itinerary_id = result3.get("itinerary_id")
                            task_id = result3.get("task_id")
                            
                            if itinerary_id and task_id:
                                print(f"   ✅ Itinerary generation initiated")
                                print(f"      Itinerary ID: {itinerary_id}")
                                print(f"      Task ID: {task_id}")
                                
                                # Wait for completion
                                print(f"\n   ⏳ Waiting for itinerary generation...")
                                for i in range(60):
                                    await asyncio.sleep(1)
                                    task_response = await client.get(
                                        f"{self.base_url}/api/v1/tasks/{task_id}"
                                    )
                                    
                                    if task_response.status_code == 200:
                                        task_data = task_response.json()
                                        status = task_data.get("status")
                                        
                                        if status == "completed":
                                            # Check itinerary for context preservation
                                            itinerary_response = await client.get(
                                                f"{self.base_url}/api/v1/itineraries/{itinerary_id}"
                                            )
                                            
                                            if itinerary_response.status_code == 200:
                                                itinerary = itinerary_response.json()
                                                
                                                # Verify context preservation
                                                destination = itinerary.get("destination_city", "").lower()
                                                budget = itinerary.get("budget_amount")
                                                duration = len(itinerary.get("daily_plans", []))
                                                
                                                context_preserved = (
                                                    "phuket" in destination or "ภูเก็ต" in destination
                                                ) and (
                                                    budget and 15000 <= float(budget) <= 25000
                                                ) and (
                                                    duration == 3
                                                )
                                                
                                                context_result["context_preserved"] = context_preserved
                                                context_result["final_itinerary_includes_context"] = True
                                                
                                                print(f"\n   🔍 Verifying context retention:")
                                                print(f"      Destination: {itinerary.get('destination_city')} {'✅' if 'phuket' in destination.lower() or 'ภูเก็ต' in destination else '❌'}")
                                                print(f"      Budget: {budget} THB {'✅' if budget and 15000 <= float(budget) <= 25000 else '❌'}")
                                                print(f"      Duration: {duration} days {'✅' if duration == 3 else '❌'}")
                                                
                                                if context_preserved:
                                                    print(f"\n   ✅ Context fully retained across 3 turns!")
                                                else:
                                                    print(f"\n   ⚠️  Context may not be fully retained")
                                            break
                                        elif status == "failed":
                                            print(f"   ❌ Task failed")
                                            break

            self.test_results["context_retention_tested"] = True
            self.test_results["context_fully_retained"] = context_result["context_preserved"]
            
            return context_result

        except Exception as e:
            print(f"❌ Error testing context retention: {str(e)}")
            self.test_results["context_retention_tested"] = True
            self.test_results["context_fully_retained"] = False
            context_result["error"] = str(e)
            return context_result

    async def validate_mcp_tools_integration(
        self, task_id: str, itinerary_id: str
    ) -> dict[str, Any]:
        """Validate MCP tools integration status."""
        print("\n" + "=" * 80)
        print("🔧 STEP 3: Validating MCP Tools Integration")
        print("=" * 80)

        tools_status = {
            "WeatherTool": {"available": False, "status": "not_checked"},
            "AmadeusTool": {"available": False, "status": "not_checked"},
            "GoogleMapsTransitTool": {"available": False, "status": "not_checked"},
            "GoogleImageSearch": {"available": False, "status": "not_checked"},
            "TravelpayoutsTool": {"available": False, "status": "not_checked"},
            "FallbackSystem": {"used": False, "status": "not_checked"},
        }

        # Wait for task completion and check itinerary
        print("\n⏳ Waiting for task completion...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Poll task status
                for i in range(MAX_TASK_WAIT_SECONDS):
                    await asyncio.sleep(TASK_STATUS_POLL_INTERVAL)

                    task_response = await client.get(
                        f"{self.base_url}/api/v1/tasks/{task_id}"
                    )

                    if task_response.status_code == 200:
                        task_data = task_response.json()
                        status = task_data.get("status")
                        progress = task_data.get("progress", 0)

                        if i % STATUS_PRINT_INTERVAL == 0:
                            print(f"   [{i}s] Status: {status} | Progress: {progress}%")

                        if status == "completed":
                            print(f"\n✅ Task completed in {i} seconds")
                            self.test_results["task_completion"] = True

                            # Get itinerary details
                            itinerary_response = await client.get(
                                f"{self.base_url}/api/v1/itineraries/{itinerary_id}"
                            )

                            if itinerary_response.status_code == 200:
                                itinerary_data = itinerary_response.json()

                                # Analyze itinerary for tool usage
                                print(f"\n🔍 Analyzing Tool Usage:")

                                # Check weather data
                                if itinerary_data.get("weather_context"):
                                    tools_status["WeatherTool"]["available"] = True
                                    tools_status["WeatherTool"]["status"] = "active"
                                    print(f"   ✅ WeatherTool: Active (data present)")
                                else:
                                    tools_status["WeatherTool"]["status"] = "missing"
                                    print(f"   ⚠️  WeatherTool: Missing data")

                                # Check flights
                                if itinerary_data.get("booking_options"):
                                    booking_options = itinerary_data["booking_options"]
                                    flights = [
                                        b
                                        for b in booking_options
                                        if b.get("type") == "flight"
                                    ]
                                    if flights:
                                        tools_status["AmadeusTool"]["available"] = True
                                        tools_status["AmadeusTool"][
                                            "status"
                                        ] = "active"
                                        print(
                                            f"   ✅ AmadeusTool (flights): Active ({len(flights)} options)"
                                        )
                                    else:
                                        tools_status["AmadeusTool"][
                                            "status"
                                        ] = "limited"
                                        print(f"   ⚠️  AmadeusTool: No flights found")

                                    # Check hotels
                                    hotels = [
                                        b
                                        for b in booking_options
                                        if b.get("type") == "hotel"
                                    ]
                                    if hotels:
                                        print(
                                            f"   ✅ AmadeusTool (hotels): Active ({len(hotels)} options)"
                                        )
                                    else:
                                        print(f"   ⚠️  AmadeusTool: No hotels found")

                                # Check activities for transit and images
                                daily_plans = itinerary_data.get("daily_plans", [])
                                has_transit = False
                                has_images = False

                                for day in daily_plans:
                                    activities = day.get("activities", [])
                                    for activity in activities:
                                        if activity.get("transit_to"):
                                            has_transit = True
                                        if activity.get("image_url"):
                                            has_images = True

                                if has_transit:
                                    tools_status["GoogleMapsTransitTool"][
                                        "available"
                                    ] = True
                                    tools_status["GoogleMapsTransitTool"][
                                        "status"
                                    ] = "active"
                                    print(
                                        f"   ✅ GoogleMapsTransitTool: Active (transit data present)"
                                    )
                                else:
                                    tools_status["GoogleMapsTransitTool"][
                                        "status"
                                    ] = "missing"
                                    print(
                                        f"   ⚠️  GoogleMapsTransitTool: No transit data"
                                    )

                                if has_images:
                                    tools_status["GoogleImageSearch"][
                                        "available"
                                    ] = True
                                    tools_status["GoogleImageSearch"][
                                        "status"
                                    ] = "active"
                                    print(
                                        f"   ✅ GoogleImageSearch: Active (images present)"
                                    )
                                else:
                                    tools_status["GoogleImageSearch"][
                                        "status"
                                    ] = "missing"
                                    print(f"   ⚠️  GoogleImageSearch: No images found")

                                # Check affiliate links
                                has_affiliate = False
                                for day in daily_plans:
                                    activities = day.get("activities", [])
                                    for activity in activities:
                                        if activity.get("affiliate_url"):
                                            has_affiliate = True
                                            break

                                if has_affiliate:
                                    tools_status["TravelpayoutsTool"][
                                        "available"
                                    ] = True
                                    tools_status["TravelpayoutsTool"][
                                        "status"
                                    ] = "active"
                                    print(
                                        f"   ✅ TravelpayoutsTool: Active (affiliate links present)"
                                    )
                                else:
                                    tools_status["TravelpayoutsTool"][
                                        "status"
                                    ] = "limited"
                                    print(
                                        f"   ⚠️  TravelpayoutsTool: No affiliate links"
                                    )

                                # Check if fallback was used
                                if itinerary_data.get("metadata", {}).get(
                                    "fallback_used"
                                ):
                                    tools_status["FallbackSystem"]["used"] = True
                                    tools_status["FallbackSystem"]["status"] = "active"
                                    print(f"   ℹ️  FallbackSystem: Used for missing data")

                                return tools_status

                        elif status == "failed":
                            print(f"\n❌ Task failed: {task_data.get('error')}")
                            return tools_status

                print(
                    f"\n⏰ Timeout after {MAX_TASK_WAIT_SECONDS} seconds waiting for task completion"
                )
                return tools_status

        except Exception as e:
            print(f"❌ Error validating tools: {str(e)}")
            return tools_status

    async def validate_itinerary_completeness(
        self, itinerary_id: str
    ) -> dict[str, Any]:
        """Validate itinerary completeness."""
        print("\n" + "=" * 80)
        print("📋 STEP 4: Validating Itinerary Completeness")
        print("=" * 80)

        completeness = {
            "has_daily_plans": False,
            "days_planned": 0,
            "expected_days": 5,
            "has_activities": False,
            "total_activities": 0,
            "has_weather": False,
            "has_budget": False,
            "completeness_score": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/itineraries/{itinerary_id}"
                )

                if response.status_code == 200:
                    itinerary = response.json()

                    # Check daily plans
                    daily_plans = itinerary.get("daily_plans", [])
                    completeness["days_planned"] = len(daily_plans)
                    completeness["has_daily_plans"] = len(daily_plans) > 0

                    print(
                        f"\n📅 Daily Plans: {completeness['days_planned']}/{completeness['expected_days']} days"
                    )

                    # Check activities
                    total_activities = sum(
                        len(day.get("activities", [])) for day in daily_plans
                    )
                    completeness["total_activities"] = total_activities
                    completeness["has_activities"] = total_activities > 0

                    print(f"🎯 Activities: {total_activities} total")

                    # Check weather
                    completeness["has_weather"] = bool(
                        itinerary.get("weather_context")
                    )
                    print(
                        f"🌤️  Weather: {'✅ Present' if completeness['has_weather'] else '❌ Missing'}"
                    )

                    # Check budget
                    completeness["has_budget"] = (
                        itinerary.get("budget_amount") is not None
                    )
                    print(
                        f"💰 Budget: {'✅ Present' if completeness['has_budget'] else '❌ Missing'}"
                    )

                    # Calculate completeness score using defined weights
                    score = 0
                    if completeness["has_daily_plans"]:
                        score += SCORE_DAILY_PLANS
                    if completeness["days_planned"] == completeness["expected_days"]:
                        score += SCORE_ALL_DAYS_PLANNED
                    if completeness["has_activities"]:
                        score += SCORE_HAS_ACTIVITIES
                    if completeness["has_weather"]:
                        score += SCORE_HAS_WEATHER
                    if completeness["has_budget"]:
                        score += SCORE_HAS_BUDGET

                    completeness["completeness_score"] = score

                    print(f"\n📊 Completeness Score: {score}/100")

                    return completeness

        except Exception as e:
            print(f"❌ Error checking completeness: {str(e)}")

        return completeness

    def generate_test_report(self) -> None:
        """Generate comprehensive test report."""
        print("\n" + "=" * 80)
        print("📊 TEST REPORT: Trip Planning Strategy Validation")
        print("=" * 80)

        print(f"\n1️⃣  Server Availability:")
        print(
            f"   {'✅ PASS' if self.test_results['server_available'] else '❌ FAIL'}"
        )

        print(f"\n2️⃣  Trip Generation Request:")
        print(
            f"   {'✅ PASS' if self.test_results['request_success'] else '❌ FAIL'}"
        )

        print(f"\n3️⃣  Task Completion:")
        print(
            f"   {'✅ PASS' if self.test_results['task_completion'] else '❌ FAIL'}"
        )

        print(f"\n4️⃣  MCP Tools Integration:")
        tools_status = self.test_results.get("mcp_tools_status", {})
        if tools_status:
            for tool_name, status in tools_status.items():
                status_str = status.get("status", "unknown")
                if status_str == "active":
                    icon = "✅"
                elif status_str == "limited":
                    icon = "⚠️"
                elif status_str == "missing":
                    icon = "❌"
                else:
                    icon = "❓"
                print(f"   {icon} {tool_name}: {status_str}")

        print(f"\n5️⃣  Itinerary Completeness:")
        completeness = self.test_results.get("itinerary_completeness", {})
        if completeness:
            score = completeness.get("completeness_score", 0)
            print(f"   Score: {score}/100")
            print(
                f"   Days: {completeness.get('days_planned', 0)}/{completeness.get('expected_days', 5)}"
            )
            print(f"   Activities: {completeness.get('total_activities', 0)}")

        print(f"\n6️⃣  WebSocket Progress Tracking:")
        if self.test_results.get("websocket_tested"):
            if self.test_results.get("websocket_working"):
                print(f"   ✅ PASS - WebSocket connection and tracking working")
            else:
                print(f"   ⚠️  NOT AVAILABLE - WebSocket endpoint not accessible")
                print(f"       (This is acceptable for development)")
        else:
            print(f"   ⚠️  NOT TESTED")

        print(f"\n7️⃣  Context Retention:")
        if self.test_results.get("context_retention_tested"):
            if self.test_results.get("context_fully_retained"):
                print(f"   ✅ PASS - Context fully retained across conversation turns")
            else:
                print(f"   ⚠️  PARTIAL - Context may not be fully retained")
                print(f"       Check conversation flow for details")
        else:
            print(f"   ⚠️  NOT TESTED")

        # Overall assessment
        print(f"\n" + "=" * 80)
        overall_pass = (
            self.test_results["server_available"]
            and self.test_results["request_success"]
            and self.test_results["task_completion"]
        )

        self.test_results["overall_pass"] = overall_pass

        if overall_pass:
            print("✅ OVERALL: PASS")
            print("\nThe trip planning feature is working correctly.")
            print("Request was successful and task completed.")
            
            # Additional context info
            if self.test_results.get("context_fully_retained"):
                print("✅ Context retention is working as expected.")
            if self.test_results.get("websocket_working"):
                print("✅ WebSocket progress tracking is functional.")
        else:
            print("❌ OVERALL: FAIL")
            print("\nSome components are not working as expected.")

        print("=" * 80)

        # Save results to file
        results_file = Path(__file__).parent.parent / "test_results_strategy.json"
        with open(results_file, "w") as f:
            json.dump(self.test_results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")

    async def run_all_tests(self) -> None:
        """Run all tests in sequence."""
        print("\n" + "=" * 80)
        print("🚀 Starting Trip Planning Strategy Test Suite")
        print("=" * 80)

        # Step 1: Check server
        if not await self.check_server_availability():
            self.generate_test_report()
            return

        # Step 2: Test trip generation request
        response_data = await self.test_trip_generation_request()
        if not response_data:
            self.generate_test_report()
            return

        # Extract IDs
        task_id = response_data.get("task_id")
        itinerary_id = response_data.get("itinerary_id")

        if not task_id or not itinerary_id:
            print(
                f"\n⚠️  Missing task_id or itinerary_id in response. Cannot continue."
            )
            self.generate_test_report()
            return

        # Step 3: Try WebSocket tracking (optional)
        print("\n💡 Testing WebSocket progress tracking (optional feature)...")
        ws_result = await self.track_progress_via_websocket(task_id)
        
        # Step 3b: Validate MCP tools (use REST API tracking)
        tools_status = await self.validate_mcp_tools_integration(
            task_id, itinerary_id
        )
        self.test_results["mcp_tools_status"] = tools_status

        # Step 4: Validate completeness
        completeness = await self.validate_itinerary_completeness(itinerary_id)
        self.test_results["itinerary_completeness"] = completeness

        # Step 5: Test context retention
        print("\n💡 Testing context retention (optional feature)...")
        context_result = await self.test_context_retention()

        # Step 6: Generate report
        self.generate_test_report()


async def main():
    """Main entry point."""
    test = TripPlanningStrategyTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
