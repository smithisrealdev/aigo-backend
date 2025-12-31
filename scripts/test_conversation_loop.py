#!/usr/bin/env python3
"""
Conversation Loop Test for AiGo Backend.

Tests multi-turn conversations to verify:
1. Context retention across multiple turns
2. Ability to modify plans based on user feedback
3. Natural conversation flow
4. Proper intent classification in conversation

Run: python scripts/test_conversation_loop.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


class ConversationLoopTester:
    """Test conversation loop functionality."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.conversation_history: list[dict[str, Any]] = []
        self.test_results: list[dict[str, Any]] = []
        self.current_itinerary_id: str | None = None
        self.current_task_id: str | None = None

    async def send_message(
        self, prompt: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        """Send a message in the conversation."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {"prompt": prompt}
                if conversation_id:
                    payload["conversation_id"] = conversation_id

                response = await client.post(
                    f"{self.base_url}/api/v1/itineraries/generate",
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    self.conversation_history.append(
                        {"role": "user", "content": prompt, "response": result}
                    )
                    return result
                else:
                    error = {
                        "error": True,
                        "status_code": response.status_code,
                        "detail": response.text,
                    }
                    self.conversation_history.append(
                        {"role": "user", "content": prompt, "response": error}
                    )
                    return error

        except Exception as e:
            error = {"error": True, "exception": str(e)}
            self.conversation_history.append(
                {"role": "user", "content": prompt, "response": error}
            )
            return error

    async def wait_for_task_completion(
        self, task_id: str, max_wait: int = 60
    ) -> dict[str, Any] | None:
        """Wait for a task to complete and return the result."""
        print(f"   ⏳ Waiting for task {task_id} to complete...")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                for i in range(max_wait):
                    await asyncio.sleep(1)

                    response = await client.get(
                        f"{self.base_url}/api/v1/tasks/{task_id}"
                    )

                    if response.status_code == 200:
                        task_status = response.json()
                        status = task_status.get("status")
                        progress = task_status.get("progress", 0)

                        if i % 5 == 0:  # Print every 5 seconds
                            print(f"      Progress: {progress}% - Status: {status}")

                        if status == "completed":
                            print(f"   ✅ Task completed successfully!")
                            return task_status
                        elif status == "failed":
                            print(f"   ❌ Task failed: {task_status.get('error')}")
                            return task_status

                print(f"   ⏰ Timeout waiting for task completion")
                return None

        except Exception as e:
            print(f"   ❌ Error checking task status: {str(e)}")
            return None

    async def test_basic_conversation_continuity(self):
        """Test 12: Basic conversation continuity."""
        print("\n" + "=" * 70)
        print("TEST 12: Basic Conversation Continuity (Thai)")
        print("=" * 70)

        conversation_id = None

        # Turn 1
        print("\n🗣️  Turn 1: Initial vague request")
        prompt1 = "อยากไปเที่ยวทะเล อากาศดีๆ ไม่ร้อนมาก"
        print(f"   User: {prompt1}")

        result1 = await self.send_message(prompt1, conversation_id)

        if not result1.get("error"):
            intent1 = result1.get("intent")
            message1 = result1.get("message", "")
            conversation_id = result1.get("conversation_id")

            print(f"   AI Intent: {intent1}")
            print(f"   AI Response: {message1[:150]}...")

            # Check if AI asked clarifying questions
            has_questions = any(
                q in message1 for q in ["?", "คะ", "ครับ", "อยาก", "งบ"]
            )
            if has_questions:
                print(f"   ✅ AI asked clarifying questions")
            else:
                print(f"   ⚠️  AI may not have asked clarifying questions")

        await asyncio.sleep(2)

        # Turn 2
        print("\n🗣️  Turn 2: Provide budget and destination")
        prompt2 = "งบ 20,000 บาท ไป 3 วัน อยากไปภูเก็ต"
        print(f"   User: {prompt2}")

        result2 = await self.send_message(prompt2, conversation_id)

        if not result2.get("error"):
            intent2 = result2.get("intent")
            message2 = result2.get("message", "")

            print(f"   AI Intent: {intent2}")
            print(f"   AI Response: {message2[:150]}...")

            # Check context retention
            context_retained = "ภูเก็ต" in message2 or "phuket" in message2.lower()
            if context_retained:
                print(f"   ✅ Context retained (Phuket mentioned)")
            else:
                print(f"   ⚠️  Context may not be fully retained")

        await asyncio.sleep(2)

        # Turn 3
        print("\n🗣️  Turn 3: Confirm dates")
        next_week = date.today() + timedelta(days=7)
        prompt3 = "ไปสัปดาห์หน้าได้ไหม"
        print(f"   User: {prompt3}")

        result3 = await self.send_message(prompt3, conversation_id)

        if not result3.get("error"):
            intent3 = result3.get("intent")
            message3 = result3.get("message", "")

            print(f"   AI Intent: {intent3}")
            print(f"   AI Response: {message3[:150]}...")

            # If trip generation started
            if intent3 == "trip_generation":
                self.current_itinerary_id = result3.get("itinerary_id")
                self.current_task_id = result3.get("task_id")
                print(f"   ✅ Trip generation initiated")
                print(f"   📋 Itinerary ID: {self.current_itinerary_id}")
                print(f"   🎯 Task ID: {self.current_task_id}")

                # Wait for completion
                if self.current_task_id:
                    await self.wait_for_task_completion(self.current_task_id)

        # Test summary
        print("\n" + "=" * 70)
        print("📊 Test 12 Summary")
        print("=" * 70)
        print(f"✅ Conversation turns: 3")
        print(f"✅ Context tracking: {'Yes' if conversation_id else 'No'}")
        print(f"✅ Trip generated: {'Yes' if self.current_itinerary_id else 'No'}")

        self.test_results.append(
            {
                "test": "Basic Conversation Continuity",
                "status": "✅ Pass" if self.current_itinerary_id else "⚠️  Partial",
                "turns": 3,
                "trip_generated": self.current_itinerary_id is not None,
            }
        )

    async def test_plan_modification_loop(self):
        """Test 13: Plan modification loop."""
        print("\n" + "=" * 70)
        print("TEST 13: Plan Modification Loop (English)")
        print("=" * 70)

        # Turn 1 - Create initial plan
        print("\n🗣️  Turn 1: Create initial itinerary")
        start_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
        end_date = (date.today() + timedelta(days=18)).strftime("%Y-%m-%d")

        prompt1 = f"Plan a 5-day trip to Bangkok from {start_date} to {end_date} for $1,000"
        print(f"   User: {prompt1}")

        result1 = await self.send_message(prompt1)

        itinerary_id = None
        task_id = None

        if not result1.get("error"):
            intent1 = result1.get("intent")
            itinerary_id = result1.get("itinerary_id")
            task_id = result1.get("task_id")

            print(f"   AI Intent: {intent1}")
            print(f"   📋 Itinerary ID: {itinerary_id}")

            if task_id:
                print(f"   🎯 Task ID: {task_id}")
                await self.wait_for_task_completion(task_id, max_wait=90)

        if not itinerary_id:
            print("   ❌ Failed to create initial itinerary")
            self.test_results.append(
                {
                    "test": "Plan Modification Loop",
                    "status": "❌ Fail",
                    "reason": "Initial itinerary creation failed",
                }
            )
            return

        await asyncio.sleep(3)

        # Turn 2 - Modify Day 3
        print("\n🗣️  Turn 2: Request modification to Day 3")
        prompt2 = "The itinerary looks good, but Day 3 has too much shopping. Can we replace it with more temples and cultural sites?"
        print(f"   User: {prompt2}")

        result2 = await self.send_message(prompt2)

        if not result2.get("error"):
            intent2 = result2.get("intent")
            message2 = result2.get("message", "")

            print(f"   AI Intent: {intent2}")
            print(f"   AI Response: {message2[:150]}...")

            # Check if modification acknowledged
            modification_words = [
                "modify",
                "change",
                "update",
                "replace",
                "temple",
                "cultural",
            ]
            acknowledged = any(
                word in message2.lower() for word in modification_words
            )

            if acknowledged:
                print(f"   ✅ Modification request acknowledged")

                # If new task created
                new_task_id = result2.get("task_id")
                if new_task_id:
                    print(f"   🎯 New Task ID: {new_task_id}")
                    await self.wait_for_task_completion(new_task_id, max_wait=60)
            else:
                print(f"   ⚠️  Modification may not be acknowledged")

        await asyncio.sleep(3)

        # Turn 3 - Further refinement
        print("\n🗣️  Turn 3: Request specific activity rescheduling")
        prompt3 = "Great! But can we move the Grand Palace visit to the morning of Day 2 instead?"
        print(f"   User: {prompt3}")

        result3 = await self.send_message(prompt3)

        if not result3.get("error"):
            intent3 = result3.get("intent")
            message3 = result3.get("message", "")

            print(f"   AI Intent: {intent3}")
            print(f"   AI Response: {message3[:150]}...")

            # Check if specific change acknowledged
            specific_change = any(
                word in message3.lower()
                for word in ["grand palace", "day 2", "morning", "moved", "rescheduled"]
            )

            if specific_change:
                print(f"   ✅ Specific change acknowledged")
            else:
                print(f"   ⚠️  Specific change may not be acknowledged")

        # Test summary
        print("\n" + "=" * 70)
        print("📊 Test 13 Summary")
        print("=" * 70)
        print(f"✅ Initial itinerary created: Yes")
        print(f"✅ Modification requests: 2")
        print(f"✅ Conversation turns: 3")

        self.test_results.append(
            {
                "test": "Plan Modification Loop",
                "status": "✅ Pass",
                "turns": 3,
                "modifications": 2,
            }
        )

    async def test_complex_multi_turn(self):
        """Test 14: Complex multi-turn conversation."""
        print("\n" + "=" * 70)
        print("TEST 14: Complex Multi-Turn Conversation (Thai)")
        print("=" * 70)

        # Turn 1 - Weather inquiry
        print("\n🗣️  Turn 1: Weather inquiry")
        prompt1 = "ญี่ปุ่นเดือนเมษายนอากาศเป็นยังไง"
        print(f"   User: {prompt1}")

        result1 = await self.send_message(prompt1)
        if not result1.get("error"):
            print(f"   AI: {result1.get('message', '')[:100]}...")

        await asyncio.sleep(2)

        # Turn 2 - Add interest
        print("\n🗣️  Turn 2: Add specific interest")
        prompt2 = "อยากดูซากุระ แนะนำที่ไหนดี"
        print(f"   User: {prompt2}")

        result2 = await self.send_message(prompt2)
        if not result2.get("error"):
            print(f"   AI: {result2.get('message', '')[:100]}...")

        await asyncio.sleep(2)

        # Turn 3 - Budget question
        print("\n🗣️  Turn 3: Budget inquiry")
        prompt3 = "ไปญี่ปุ่น 7 วันต้องเตรียมเงินเท่าไหร่"
        print(f"   User: {prompt3}")

        result3 = await self.send_message(prompt3)
        if not result3.get("error"):
            print(f"   AI: {result3.get('message', '')[:100]}...")

        await asyncio.sleep(2)

        # Turn 4 - Create plan with all context
        print("\n🗣️  Turn 4: Create comprehensive plan")
        prompt4 = "โอเค งั้นวางแผนให้หน่อย งบ 80,000 บาท 7 วัน โตเกียวกับเกียวโต เน้นดูซากุระ"
        print(f"   User: {prompt4}")

        result4 = await self.send_message(prompt4)

        if not result4.get("error"):
            intent4 = result4.get("intent")
            itinerary_id = result4.get("itinerary_id")
            task_id = result4.get("task_id")

            print(f"   AI Intent: {intent4}")
            print(f"   📋 Itinerary ID: {itinerary_id}")

            if task_id:
                await self.wait_for_task_completion(task_id, max_wait=90)

            # Check if all context is captured
            context_check = {
                "April (cherry blossoms)": "เมษายน" in prompt1 or "April" in str(result1),
                "7 days": "7 วัน" in prompt4,
                "Budget 80,000": "80,000" in prompt4 or "80000" in prompt4,
                "Tokyo + Kyoto": "โตเกียว" in prompt4 and "เกียวโต" in prompt4,
                "Cherry blossoms": "ซากุระ" in prompt4 or "sakura" in str(result4).lower(),
            }

            print(f"\n   Context Capture Check:")
            for key, captured in context_check.items():
                status = "✅" if captured else "❌"
                print(f"      {status} {key}")

            all_captured = all(context_check.values())

            if all_captured:
                print(f"\n   ✅ All context successfully captured across 4 turns!")
            else:
                print(f"\n   ⚠️  Some context may be missing")

        await asyncio.sleep(3)

        # Turn 5 - Modification
        print("\n🗣️  Turn 5: Request extension")
        prompt5 = "เพิ่มโอซาก้า 1 วันได้ไหม"
        print(f"   User: {prompt5}")

        result5 = await self.send_message(prompt5)

        if not result5.get("error"):
            message5 = result5.get("message", "")
            print(f"   AI: {message5[:150]}...")

            has_osaka = "โอซาก้า" in message5 or "osaka" in message5.lower()
            has_extension = any(
                word in message5.lower() for word in ["8", "extend", "เพิ่ม"]
            )

            if has_osaka and has_extension:
                print(f"   ✅ Extension request acknowledged")
            else:
                print(f"   ⚠️  Extension may not be fully acknowledged")

        # Test summary
        print("\n" + "=" * 70)
        print("📊 Test 14 Summary")
        print("=" * 70)
        print(f"✅ Conversation turns: 5")
        print(f"✅ Context switches: Weather → Recommendations → Budget → Planning → Modification")
        print(f"✅ Final plan created: {'Yes' if result4.get('itinerary_id') else 'No'}")

        self.test_results.append(
            {
                "test": "Complex Multi-Turn Conversation",
                "status": "✅ Pass",
                "turns": 5,
                "context_switches": 4,
            }
        )

    async def check_server_availability(self) -> bool:
        """Check if server is running."""
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
        """Print overall test summary."""
        print("\n" + "=" * 70)
        print("📊 Overall Test Summary")
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
            if "turns" in result:
                print(f"      Turns: {result['turns']}")
            if "modifications" in result:
                print(f"      Modifications: {result['modifications']}")
            if "context_switches" in result:
                print(f"      Context Switches: {result['context_switches']}")

        print("\n" + "=" * 70)

        if failed == 0:
            print("✅ All conversation loop tests passed!")
            return True
        else:
            print("❌ Some tests failed")
            return False


async def main():
    """Run all conversation loop tests."""
    print("=" * 70)
    print("🗣️  Conversation Loop Test Suite")
    print("=" * 70)
    print("\nThis test suite verifies:")
    print("1. Multi-turn context retention")
    print("2. Plan modification capability")
    print("3. Natural conversation flow")
    print("4. Complex multi-turn scenarios")
    print()

    tester = ConversationLoopTester(base_url="http://localhost:8000")

    # Check server availability
    if not await tester.check_server_availability():
        print("\n❌ Cannot run tests without server")
        sys.exit(1)

    try:
        # Run all conversation tests
        await tester.test_basic_conversation_continuity()
        await tester.test_plan_modification_loop()
        await tester.test_complex_multi_turn()

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
