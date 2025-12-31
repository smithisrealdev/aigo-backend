#!/usr/bin/env python3
"""
Quick test script for OpenWeatherMap API integration.
Run: python scripts/test_weather_api.py
"""

import asyncio
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test data
TEST_LOCATIONS = [
    {"name": "Bangkok", "location": "Bangkok"},
    {"name": "Tokyo", "location": "Tokyo"},
    {"name": "Bangkok (coordinates)", "location": "13.7563,100.5018"},
]


async def test_weather_api():
    """Test OpenWeatherMap API integration."""
    # Load settings after path setup
    from app.core.config import settings
    from app.domains.itinerary.tools.weather import WeatherClient, WeatherTool

    print("=" * 60)
    print("🌤️  Testing OpenWeatherMap API Integration")
    print("=" * 60)

    # Check config
    print(f"\n📋 Configuration:")
    api_key = settings.WEATHER_API_KEY
    base_url = settings.WEATHER_API_BASE_URL
    print(f"   API Key: {'✅ Set (' + api_key[:10] + '...)' if api_key else '❌ Missing'}")
    print(f"   Base URL: {base_url}")

    if not api_key:
        print("\n❌ Error: Missing API credentials!")
        print("   Set WEATHER_API_KEY in .env")
        print("\n📚 Setup Instructions:")
        print("   1. Sign up at: https://openweathermap.org/api")
        print("   2. Get API key from: https://home.openweathermap.org/api_keys")
        print("   3. Add to .env: WEATHER_API_KEY=your_api_key")
        return False

    print("=" * 60)
    print("TEST 1: Current Weather API")
    print("=" * 60)

    all_success = True

    for test_case in TEST_LOCATIONS:
        print(f"\n🧪 Testing: {test_case['name']}")
        print(f"   Location: {test_case['location']}")

        try:
            async with WeatherClient(api_key=api_key, base_url=base_url) as client:
                result = await client.get_current_weather(
                    location=test_case["location"],
                    units="metric",
                )

                print(f"   ✅ Success!")
                print(f"   📍 Location: {result.location}, {result.country}")
                print(f"   🌡️  Temperature: {result.temperature}°C (feels like {result.feels_like}°C)")
                print(f"   ☁️  Condition: {result.condition.main} - {result.condition.description}")
                print(f"   💧 Humidity: {result.humidity}%")
                print(f"   💨 Wind Speed: {result.wind_speed} m/s")
                print(f"   👁️  Visibility: {result.visibility}m")
                if result.advisory:
                    print(f"   💡 Advisory: {result.advisory}")

        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
            all_success = False

    print("\n" + "=" * 60)
    print("TEST 2: Weather Forecast API")
    print("=" * 60)

    # Test forecast for next 5 days
    start_date = date.today()
    end_date = start_date + timedelta(days=5)

    print(f"\n🧪 Testing: Weather Forecast")
    print(f"   Location: Bangkok")
    print(f"   Period: {start_date} to {end_date}")

    try:
        async with WeatherClient(api_key=api_key, base_url=base_url) as client:
            result = await client.get_forecast(
                location="Bangkok",
                start_date=str(start_date),
                end_date=str(end_date),
                units="metric",
            )

            print(f"   ✅ Success!")
            print(f"   📍 Location: {result.location}, {result.country}")
            print(f"   🌍 Coordinates: ({result.latitude}, {result.longitude})")
            print(f"   📅 Daily Forecasts: {len(result.daily_forecasts)} days")

            if result.period_summary:
                print(f"   📊 Summary: {result.period_summary}")

            if result.packing_suggestions:
                print(f"   🎒 Packing Suggestions:")
                for item in result.packing_suggestions:
                    print(f"      - {item}")

            print(f"\n   📆 Daily Breakdown:")
            for day in result.daily_forecasts:
                print(f"      {day.day_name} ({day.date}):")
                print(f"         Temp: {day.temp_min}°C - {day.temp_max}°C")
                print(f"         Condition: {day.condition.description}")
                print(f"         Rain Probability: {day.precipitation_probability * 100:.0f}%")

    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        all_success = False

    print("\n" + "=" * 60)
    print("TEST 3: LangChain Tools Integration")
    print("=" * 60)

    print(f"\n🧪 Testing: WeatherCurrentTool")
    try:
        result = await WeatherTool.current._arun(
            location="Tokyo",
            units="metric",
        )
        print(f"   ✅ Success!")
        print(f"   📍 Location: {result['location']}")
        print(f"   🌡️  Temperature: {result['temperature']}°C")
        print(f"   ☁️  Condition: {result['condition']['description']}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        all_success = False

    print(f"\n🧪 Testing: WeatherForecastTool")
    try:
        result = await WeatherTool.forecast._arun(
            location="Tokyo",
            start_date=str(start_date),
            end_date=str(end_date),
            units="metric",
        )
        print(f"   ✅ Success!")
        print(f"   📍 Location: {result['location']}")
        print(f"   📅 Forecast Days: {len(result['daily_forecasts'])}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        all_success = False

    print("\n" + "=" * 60)
    print("🎯 Test Summary")
    print("=" * 60)

    if all_success:
        print("\n✅ All tests passed!")
        print("\n📚 Available Tools:")
        print("   - WeatherTool.current: Get current weather conditions")
        print("   - WeatherTool.forecast: Get weather forecast for date range")
        print("\n📖 MCP Tool Contract:")
        print(f"   Tool Name: {WeatherTool.current.name}")
        print(f"   Description: {WeatherTool.current.description[:100]}...")
        print(f"\n   Tool Name: {WeatherTool.forecast.name}")
        print(f"   Description: {WeatherTool.forecast.description[:100]}...")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False


def main():
    """Run the tests."""
    try:
        success = asyncio.run(test_weather_api())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
