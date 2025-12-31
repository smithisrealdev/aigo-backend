#!/usr/bin/env python3
"""
Test script for itinerary generation with booking options

This test validates:
1. Location enrichment (Google Places API)
2. Flight options with Amadeus data + Travelpayouts links
3. Hotel options with proper booking URLs
4. Daily booking recommendations for travel days
5. Daily tips generation

Run: python3 scripts/test_itinerary_booking_options.py
"""

import asyncio
import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Import the planner components
from app.domains.itinerary.services.planner_graph import run_planner, _enrich_location_with_places


async def test_itinerary_generation():
    """Test itinerary generation with all new features."""
    
    print("=" * 80)
    print("🧪 Testing Itinerary Generation with Booking Options")
    print("=" * 80)
    
    # Create test request - Multi-city trip to test travel day detection
    start_date = date.today() + timedelta(days=7)
    end_date = start_date + timedelta(days=4)
    
    itinerary_id = str(uuid.uuid4())
    user_prompt = f"""วางแผนเที่ยว Tokyo และ Osaka 5 วัน 4 คืน
    - วันที่ 1-2: Tokyo (เที่ยววัด, ช้อปปิ้ง)
    - วันที่ 3: เดินทางจาก Tokyo ไป Osaka
    - วันที่ 4-5: Osaka (อาหาร, Universal Studios)
    งบประมาณ 50,000 บาท
    เดินทางจากกรุงเทพ
    วันที่: {start_date} ถึง {end_date}"""
    
    preferences = {
        "trip_type": "couple",
        "interests": ["culture", "food", "shopping"],
        "budget": "medium-high",
        "origin": "Bangkok, Thailand",
        "destination": "Tokyo, Japan",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "travelers": 2
    }
    
    print(f"\n📋 Test Request:")
    print(f"   Itinerary ID: {itinerary_id}")
    print(f"   Prompt: {user_prompt[:100]}...")
    print(f"   Origin: Bangkok, Thailand")
    print(f"   Destinations: Tokyo → Osaka")
    print(f"   Dates: {start_date} to {end_date}")
    print(f"   Travelers: 2")
    
    # Run the planning
    print("\n🚀 Running itinerary generation...")
    print("-" * 40)
    
    async def progress_callback(step: str, progress: int, message: str):
        print(f"   [{progress}%] {step}: {message}")
    
    try:
        result = await run_planner(
            itinerary_id=itinerary_id,
            user_prompt=user_prompt,
            user_id="test_user_001",
            preferences=preferences,
            progress_callback=progress_callback
        )
        
        print("\n" + "=" * 80)
        print("📊 RESULTS")
        print("=" * 80)
        
        # Check basic structure
        print("\n🔍 Basic Structure Check:")
        print(f"   ✅ Has response: {result.response is not None}")
        print(f"   ✅ Has daily_plans: {len(result.daily_plans)} days")
        print(f"   ✅ Has flight_options: {len(result.flight_options)} flights")
        print(f"   ✅ Has hotel_options: {len(result.hotel_options)} hotels")
        print(f"   ✅ Has activities_option: {len(result.activities_option)} activities")
        
        # Check flight options
        print("\n✈️  Flight Options:")
        if result.flight_options:
            for i, flight in enumerate(result.flight_options[:3], 1):
                print(f"\n   Flight {i}:")
                print(f"      Airline: {flight.airline}")
                print(f"      Route: {flight.departure_city} → {flight.arrival_city}")
                print(f"      Price: {flight.price} {flight.currency}")
                print(f"      Booking URL: {flight.booking_url[:80] if flight.booking_url else 'N/A'}...")
        else:
            print("   ⚠️  No flight options found")
        
        # Check hotel options
        print("\n🏨 Hotel Options:")
        if result.hotel_options:
            for i, hotel in enumerate(result.hotel_options[:3], 1):
                print(f"\n   Hotel {i}:")
                print(f"      Name: {hotel.name}")
                print(f"      Location: {hotel.location}")
                print(f"      Price: {hotel.price_per_night} {hotel.currency}/night")
                print(f"      Rating: {hotel.rating}")
                print(f"      Booking URL: {hotel.booking_url[:80] if hotel.booking_url else 'N/A'}...")
        else:
            print("   ⚠️  No hotel options found")
        
        # Check daily plans with booking recommendations
        print("\n📅 Daily Plans with Booking Recommendations:")
        for i, day in enumerate(result.daily_plans, 1):
            print(f"\n   Day {i} ({day.date}):")
            print(f"      Location: {day.location_city or 'Unknown'}, {day.location_country or 'Unknown'}")
            print(f"      Is Travel Day: {'Yes ✈️' if day.is_travel_day else 'No'}")
            if day.is_travel_day:
                print(f"      Travel: {day.travel_from} → {day.travel_to}")
            
            # Activities
            print(f"      Activities: {len(day.activities)}")
            for j, activity in enumerate(day.activities[:2], 1):
                print(f"         {j}. {activity.title}")
                if activity.location:
                    print(f"            Location: {activity.location.name or 'N/A'}")
                    print(f"            Coords: ({activity.location.latitude}, {activity.location.longitude})")
                    print(f"            Place ID: {activity.location.google_place_id or 'N/A'}")
            
            # Recommended flights for travel days
            if day.recommended_flights:
                print(f"      Recommended Flights: {len(day.recommended_flights)}")
                for flight in day.recommended_flights[:1]:
                    print(f"         - {flight.get('airline', 'N/A')}: {flight.get('departure_city')} → {flight.get('arrival_city')} ({flight.get('price', 'N/A')} {flight.get('currency', '')})")
            
            # Recommended hotel
            if day.recommended_hotel:
                hotel = day.recommended_hotel
                print(f"      Recommended Hotel: {hotel.get('name', 'N/A')} ({hotel.get('price_per_night', 'N/A')} {hotel.get('currency', '')}/night)")
            
            # Daily tips
            if day.daily_tips:
                print(f"      Daily Tips: {len(day.daily_tips)}")
                for tip in day.daily_tips[:2]:
                    print(f"         - {tip}")
        
        # Check activities with location enrichment
        print("\n📍 Location Enrichment Check:")
        enriched_count = 0
        total_activities = 0
        for day in result.daily_plans:
            for activity in day.activities:
                total_activities += 1
                if activity.location and activity.location.google_place_id:
                    enriched_count += 1
        
        print(f"   Activities with Google Place ID: {enriched_count}/{total_activities}")
        print(f"   Enrichment Rate: {(enriched_count/total_activities*100) if total_activities > 0 else 0:.1f}%")
        
        # Summary
        print("\n" + "=" * 80)
        print("📋 TEST SUMMARY")
        print("=" * 80)
        
        checks = {
            "Has daily plans": len(result.daily_plans) > 0,
            "Has flight options": len(result.flight_options) > 0,
            "Has hotel options": len(result.hotel_options) > 0,
            "Has activities": any(len(d.activities) > 0 for d in result.daily_plans),
            "Flight has booking URL": any(f.booking_url for f in result.flight_options) if result.flight_options else False,
            "Hotel has booking URL": any(h.booking_url for h in result.hotel_options) if result.hotel_options else False,
            "Activities have titles": all(a.title and a.title != "Activity" for d in result.daily_plans for a in d.activities),
            "Location enrichment": enriched_count > 0,
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")
        
        passed = sum(checks.values())
        total = len(checks)
        print(f"\n   Overall: {passed}/{total} checks passed ({passed/total*100:.0f}%)")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print(f"\n⚠️  {total - passed} check(s) failed")
        
        # Print raw JSON for inspection
        print("\n" + "=" * 80)
        print("📄 RAW JSON OUTPUT (first daily plan)")
        print("=" * 80)
        if result.daily_plans:
            first_day = result.daily_plans[0]
            print(json.dumps({
                "date": first_day.date,
                "location_city": first_day.location_city,
                "location_country": first_day.location_country,
                "is_travel_day": first_day.is_travel_day,
                "activities_count": len(first_day.activities),
                "first_activity": {
                    "title": first_day.activities[0].title if first_day.activities else None,
                    "location": {
                        "name": first_day.activities[0].location.name if first_day.activities and first_day.activities[0].location else None,
                        "latitude": first_day.activities[0].location.latitude if first_day.activities and first_day.activities[0].location else None,
                        "longitude": first_day.activities[0].location.longitude if first_day.activities and first_day.activities[0].location else None,
                        "google_place_id": first_day.activities[0].location.google_place_id if first_day.activities and first_day.activities[0].location else None,
                    } if first_day.activities and first_day.activities[0].location else None
                } if first_day.activities else None,
                "recommended_hotel": first_day.recommended_hotel,
                "daily_tips": first_day.daily_tips[:3] if first_day.daily_tips else []
            }, indent=2, ensure_ascii=False, default=str))
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_location_enrichment():
    """Test Google Places location enrichment directly."""
    
    print("\n" + "=" * 80)
    print("🧪 Testing Location Enrichment (Google Places API)")
    print("=" * 80)
    
    from app.domains.itinerary.services.planner_graph import _enrich_location_with_places
    
    test_cases = [
        ("Senso-ji Temple", "Asakusa", "Tokyo"),
        ("Shibuya Crossing", "Shibuya", "Tokyo"),
        ("Dotonbori", "Dotonbori", "Osaka"),
        ("Universal Studios Japan", "Osaka Bay", "Osaka"),
    ]
    
    for title, location_hint, city in test_cases:
        print(f"\n🔍 Searching: {title} in {city}")
        result = await _enrich_location_with_places(title, location_hint, city)
        
        if result:
            print(f"   ✅ Found: {result.name or 'N/A'}")
            print(f"   📍 Address: {result.address or 'N/A'}")
            print(f"   🌐 Coords: ({result.latitude}, {result.longitude})")
            print(f"   🆔 Place ID: {result.google_place_id or 'N/A'}")
            print(f"   ⭐ Rating: {result.rating or 'N/A'}")
        else:
            print(f"   ❌ Not found")


if __name__ == "__main__":
    print("\n" + "🚀" * 40)
    print("    AIGO ITINERARY BOOKING OPTIONS TEST")
    print("🚀" * 40 + "\n")
    
    # Run location enrichment test first
    asyncio.run(test_location_enrichment())
    
    # Then run full itinerary test
    asyncio.run(test_itinerary_generation())
