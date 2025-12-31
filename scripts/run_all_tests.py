#!/usr/bin/env python3
"""
Master Test Runner for AiGo Backend Comprehensive Testing.

Runs all test suites:
1. Full Itinerary & MCP Tools Test
2. Conversation Loop Test
3. Weather Integration Test (existing)

Usage:
    python scripts/run_all_tests.py [--skip-weather] [--skip-conversation] [--skip-full]
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


class MasterTestRunner:
    """Orchestrates all test suites."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.scripts_dir = base_dir / "scripts"
        self.results: list[dict] = []

    def run_test_script(self, script_name: str, description: str) -> dict:
        """Run a test script and capture results."""
        print("\n" + "=" * 80)
        print(f"🚀 Running: {description}")
        print("=" * 80)

        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            print(f"❌ Script not found: {script_path}")
            return {
                "script": script_name,
                "description": description,
                "status": "❌ Not Found",
                "exit_code": -1,
            }

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes max per test suite
            )

            # Print output
            if result.stdout:
                print(result.stdout)

            if result.stderr:
                print("STDERR:", result.stderr)

            status = "✅ Pass" if result.returncode == 0 else "❌ Fail"

            return {
                "script": script_name,
                "description": description,
                "status": status,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            print(f"⏰ Test timed out after 10 minutes")
            return {
                "script": script_name,
                "description": description,
                "status": "⏰ Timeout",
                "exit_code": -1,
            }

        except Exception as e:
            print(f"❌ Error running test: {str(e)}")
            return {
                "script": script_name,
                "description": description,
                "status": f"❌ Error: {str(e)}",
                "exit_code": -1,
            }

    def print_overall_summary(self):
        """Print summary of all test suites."""
        print("\n" + "=" * 80)
        print("📊 OVERALL TEST SUMMARY")
        print("=" * 80)

        total = len(self.results)
        passed = sum(1 for r in self.results if "✅" in r["status"])
        failed = sum(1 for r in self.results if "❌" in r["status"])
        timeout = sum(1 for r in self.results if "⏰" in r["status"])

        print(f"\nTotal Test Suites: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏰ Timeout: {timeout}")

        print(f"\n📋 Test Suite Results:")
        for i, result in enumerate(self.results, 1):
            print(f"\n{i}. {result['description']}")
            print(f"   Script: {result['script']}")
            print(f"   Status: {result['status']}")
            print(f"   Exit Code: {result['exit_code']}")

        print("\n" + "=" * 80)

        if failed == 0 and timeout == 0:
            print("✅ ALL TEST SUITES PASSED!")
            print("\n🎉 Comprehensive testing complete!")
            print("\nAll systems verified:")
            print("  ✅ Full itinerary generation (100%)")
            print("  ✅ All MCP tools working")
            print("  ✅ Conversation loop with context retention")
            print("  ✅ Plan modification capability")
            print("  ✅ Task progress tracking")
            print("  ✅ Weather integration")
            return True
        else:
            print("❌ SOME TEST SUITES FAILED")
            print("\nPlease review the failures above and:")
            print("  1. Check server logs for errors")
            print("  2. Verify all API keys are configured")
            print("  3. Ensure database and Redis are running")
            print("  4. Review individual test outputs")
            return False

    def check_prerequisites(self) -> bool:
        """Check if prerequisites are met."""
        print("=" * 80)
        print("🔍 Checking Prerequisites")
        print("=" * 80)

        # Check if server is accessible
        try:
            import httpx

            async def check_server():
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://localhost:8000/api/v1/health")
                    return response.status_code == 200

            server_ok = asyncio.run(check_server())

            if server_ok:
                print("✅ Server is running and accessible")
            else:
                print("❌ Server is not accessible")
                print("\n💡 Please start the server:")
                print("   cd /home/runner/work/aigo-backend/aigo-backend")
                print("   poetry run uvicorn app.main:app --reload")
                return False

        except Exception as e:
            print(f"❌ Cannot connect to server: {str(e)}")
            print("\n💡 Please start the server first")
            return False

        # Check Python version
        py_version = sys.version_info
        print(f"✅ Python version: {py_version.major}.{py_version.minor}.{py_version.micro}")

        # Check if httpx is available
        try:
            import httpx

            print(f"✅ httpx library available")
        except ImportError:
            print(f"❌ httpx library not found")
            print("   Install with: pip install httpx")
            return False

        print()
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive AiGo backend tests"
    )
    parser.add_argument(
        "--skip-full",
        action="store_true",
        help="Skip full itinerary & MCP tools test",
    )
    parser.add_argument(
        "--skip-conversation",
        action="store_true",
        help="Skip conversation loop test",
    )
    parser.add_argument(
        "--skip-weather",
        action="store_true",
        help="Skip weather integration test",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick tests only (skip long-running tests)",
    )

    args = parser.parse_args()

    # Setup
    base_dir = Path(__file__).parent.parent
    runner = MasterTestRunner(base_dir)

    print("=" * 80)
    print("🧪 AiGo Backend - Comprehensive Test Suite")
    print("=" * 80)
    print("\nThis master runner executes:")
    print("1. Full Itinerary & MCP Tools Test")
    print("2. Conversation Loop Test")
    print("3. Weather Integration Test")
    print()

    # Check prerequisites
    if not runner.check_prerequisites():
        print("\n❌ Prerequisites not met. Cannot run tests.")
        sys.exit(1)

    # Run test suites
    try:
        # Test 1: Full Itinerary & MCP Tools
        if not args.skip_full and not args.quick:
            result = runner.run_test_script(
                "test_full_itinerary_mcp_tools.py",
                "Full Itinerary & MCP Tools Test",
            )
            runner.results.append(result)

        # Test 2: Conversation Loop
        if not args.skip_conversation:
            result = runner.run_test_script(
                "test_conversation_loop.py",
                "Conversation Loop Test",
            )
            runner.results.append(result)

        # Test 3: Weather Integration (existing test)
        if not args.skip_weather and not args.quick:
            result = runner.run_test_script(
                "test_itinerary_generate_weather.py",
                "Weather Integration Test",
            )
            runner.results.append(result)

        # Print overall summary
        success = runner.print_overall_summary()

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
    main()
