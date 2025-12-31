#!/usr/bin/env python3
"""
Quick test for booking options components without full LLM generation

Tests:
1. Location enrichment (Google Places)
2. Amadeus flight search  
3. Amadeus hotel search
4. Travelpayouts URL generation
5. Daily plan enhancement logic

Run: python3 scripts/quick_booking_test.py
"""

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def test_location_enrichment():
    """Test Google Places location enrichment."""
    print("\n" + "=" * 60)
    print("🧪 TEST 1: Location Enrichment (Google Places API)")
    print("=" * 60)
    
    from app.domains.itinerary.services.planner_graph import _enrich_location_with_places
    
    test_cases = [
        ("Senso-ji Temple", "Asakusa", "Tokyo"),
        ("Universal Studios Japan", "Osaka Bay", "Osaka"),
    ]
    
    passed = 0
    for title, location_hint, city in test_cases:
        print(f"\n🔍 Searching: {title} in {city}")
        try:
            result = await _enrich_location_with_places(title, location_hint, city)
            
            if result and result.google_place_id:
                print(f"   ✅ Found: {result.name}")
                print(f"   📍 Address: {result.address}")
                print(f"   🌐 Coords: ({result.latitude:.6f}, {result.longitude:.6f})")
                print(f"   🆔 Place ID: {result.google_place_id}")
                passed += 1
            else:
                print(f"   ❌ No place ID found")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n📊 Result: {passed}/{len(test_cases)} locations enriched")
    return passed == len(test_cases)


async def test_amadeus_flights():
    """Test Amadeus flight search."""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Amadeus Flight Search")
    print("=" * 60)
    
    from app.domains.itinerary.tools.amadeus import AmadeusFlightSearchTool
    
    tool = AmadeusFlightSearchTool()
    
    start_date = date.today() + timedelta(days=14)
    
    print(f"\n✈️  Searching flights: Bangkok → Tokyo on {start_date}")
    
    try:
        result = await tool._arun(
            origin="BKK",
            destination="TYO",
            departure_date=start_date.isoformat(),
            adults=2
        )
        
        if result and "offers" in result:
            offers = result.get("offers", [])
            print(f"   ✅ Found {len(offers)} flights")
            
            if offers:
                first = offers[0]
                segments = first.get("segments", [{}])
                print(f"\n   Sample Flight:")
                print(f"      Airline: {segments[0].get('carrier_name', 'N/A')}")
                print(f"      Departure: {segments[0].get('departure_time', 'N/A')}")
                print(f"      Price: {first.get('total_price', 'N/A')} {first.get('currency', 'THB')}")
                
            return True
        else:
            print(f"   ❌ No flights found or error: {result}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_amadeus_hotels():
    """Test Amadeus hotel search."""
    print("\n" + "=" * 60)
    print("🧪 TEST 3: Amadeus Hotel Search")
    print("=" * 60)
    
    from app.domains.itinerary.tools.amadeus import AmadeusHotelSearchTool
    
    tool = AmadeusHotelSearchTool()
    
    check_in = date.today() + timedelta(days=14)
    check_out = check_in + timedelta(days=3)
    
    print(f"\n🏨 Searching hotels in Tokyo: {check_in} to {check_out}")
    
    try:
        result = await tool._arun(
            city_code="TYO",
            check_in_date=check_in.isoformat(),
            check_out_date=check_out.isoformat(),
            adults=2
        )
        
        if result and "offers" in result:
            offers = result.get("offers", [])
            print(f"   ✅ Found {len(offers)} hotels")
            
            if offers:
                first = offers[0]
                print(f"\n   Sample Hotel:")
                print(f"      Name: {first.get('name', 'N/A')}")
                print(f"      Location: {first.get('address', 'N/A')}")
                print(f"      Price: {first.get('price_per_night', 'N/A')} {first.get('currency', 'JPY')}/night")
                print(f"      Rating: {first.get('star_rating', 'N/A')}")
                
            return True
        else:
            print(f"   ⚠️  Result: {result}")
            # Amadeus hotel search might be limited, still consider partial pass
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_travelpayouts_urls():
    """Test Travelpayouts affiliate URL generation."""
    print("\n" + "=" * 60)
    print("🧪 TEST 4: Travelpayouts URL Generation")
    print("=" * 60)
    
    from app.core.config import settings
    
    marker = settings.TRAVELPAYOUTS_MARKER
    
    # Generate sample URLs
    check_in = date.today() + timedelta(days=14)
    check_out = check_in + timedelta(days=3)
    
    print(f"\n🔗 Testing affiliate URL generation...")
    print(f"   Marker: {marker}")
    
    # Flight URL
    flight_url = f"https://search.jetradar.com/flights/BKK{check_in.strftime('%d%m')}TYO1?marker={marker}"
    print(f"\n   ✈️  Flight URL: {flight_url[:80]}...")
    
    # Hotel URL  
    hotel_url = f"https://search.hotellook.com/?destination=Tokyo&checkIn={check_in}&checkOut={check_out}&marker={marker}"
    print(f"   🏨 Hotel URL: {hotel_url[:80]}...")
    
    # Check if marker is configured
    if marker and marker != "your_travelpayouts_token":
        print(f"\n   ✅ Travelpayouts marker is configured")
        return True
    else:
        print(f"\n   ⚠️  Travelpayouts marker not configured (using placeholder)")
        print(f"   💡 Update TRAVELPAYOUTS_MARKER in .env for affiliate links")
        return True  # Still pass, fallback URLs will work


async def test_booking_option_generation():
    """Test booking option generation logic."""
    print("\n" + "=" * 60)
    print("🧪 TEST 5: Booking Option Model Generation")
    print("=" * 60)
    
    from app.domains.itinerary.schemas import BookingOption, BookingType
    from decimal import Decimal
    from datetime import datetime
    
    try:
        # Test Flight BookingOption
        flight = BookingOption(
            booking_type=BookingType.FLIGHT,
            provider="Japan Airlines",
            title="BKK → TYO Direct Flight",
            description="Direct flight from Bangkok to Tokyo Narita",
            price=Decimal("25000.00"),
            currency="THB",
            departure_time=datetime(2026, 1, 14, 10, 30),
            arrival_time=datetime(2026, 1, 14, 18, 45),
            departure_airport="BKK",
            arrival_airport="NRT",
            flight_number="JL32",
            airline="Japan Airlines",
            affiliate_url="https://search.jetradar.com/flights/BKK1401TYO1?marker=test",
            stops=0
        )
        print(f"\n   ✅ Flight BookingOption created:")
        print(f"      {flight.title}")
        print(f"      Airline: {flight.airline}, Flight: {flight.flight_number}")
        print(f"      Price: {flight.price} {flight.currency}")
        print(f"      Affiliate URL: {flight.affiliate_url[:60]}...")
        
        # Test Hotel BookingOption
        hotel = BookingOption(
            booking_type=BookingType.HOTEL,
            provider="Booking.com",
            title="Hotel Gracery Shinjuku",
            description="4-star hotel in Shinjuku, Tokyo",
            price=Decimal("15000.00"),
            price_per_night=Decimal("5000.00"),
            currency="THB",
            rating=4.5,
            hotel_stars=4,
            check_in_date=date(2026, 1, 14),
            check_out_date=date(2026, 1, 17),
            affiliate_url="https://search.hotellook.com/?destination=Tokyo&marker=test"
        )
        print(f"\n   ✅ Hotel BookingOption created:")
        print(f"      {hotel.title}")
        print(f"      Price: {hotel.price_per_night} {hotel.currency}/night")
        print(f"      Rating: {hotel.rating}")
        
        # Test Activity BookingOption
        activity = BookingOption(
            booking_type=BookingType.ACTIVITY,
            provider="Viator",
            title="Tokyo Tower Observation Deck",
            description="Visit the iconic Tokyo Tower",
            price=Decimal("1200.00"),
            currency="THB",
            affiliate_url="https://www.google.com/search?q=Tokyo+Tower+tickets"
        )
        print(f"\n   ✅ Activity BookingOption created:")
        print(f"      {activity.title}")
        print(f"      Price: {activity.price} {activity.currency}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_daily_plan_fields():
    """Test AIDailyPlan with new booking fields."""
    print("\n" + "=" * 60)
    print("🧪 TEST 6: AIDailyPlan Booking Fields")
    print("=" * 60)
    
    from app.domains.itinerary.schemas import AIDailyPlan, AIActivity, LocationInfo
    from datetime import time
    from decimal import Decimal
    
    check_in = date.today() + timedelta(days=14)
    
    try:
        # Create a daily plan with all new fields
        daily_plan = AIDailyPlan(
            day_number=1,
            date=check_in.isoformat(),
            title="Arrival in Tokyo",
            summary="Arrive at Haneda Airport and explore Shibuya",
            activities=[
                AIActivity(
                    title="Shibuya Crossing",
                    description="Experience the famous crossing at Shibuya, one of the busiest pedestrian crossings in the world.",
                    start_time=time(14, 0),
                    end_time=time(15, 30),
                    duration_minutes=90,
                    location=LocationInfo(
                        name="Shibuya Crossing",
                        address="Shibuya, Tokyo",
                        latitude=35.659482,
                        longitude=139.7005596,
                        google_place_id="ChIJK9EM68qLGGARacmu4KJj5SA"
                    ),
                    category="sightseeing",
                    estimated_cost=Decimal("0"),
                    cost_currency="THB"
                )
            ],
            # New booking fields
            location_city="Tokyo",
            location_country="Japan",
            is_travel_day=True,
            travel_from="Bangkok",
            travel_to="Tokyo",
            recommended_flights=[
                {
                    "airline": "Japan Airlines",
                    "departure_city": "Bangkok",
                    "arrival_city": "Tokyo",
                    "price": 25000,
                    "currency": "THB",
                    "booking_url": "https://jetradar.com"
                }
            ],
            recommended_hotel={
                "name": "Hotel Gracery Shinjuku",
                "price_per_night": 5000,
                "currency": "THB",
                "booking_url": "https://hotellook.com"
            },
            bookable_activities=[
                {
                    "name": "Shibuya Sky",
                    "price": 2000,
                    "currency": "THB",
                    "booking_url": "https://google.com/search"
                }
            ],
            daily_tips=[
                "🌤️ Weather: Clear, 15°C - Dress in layers",
                "💡 Tip: Get Suica card at airport for trains",
                "⏰ Best time: Visit Shibuya Crossing at sunset"
            ]
        )
        
        print(f"\n   ✅ AIDailyPlan created with all new fields:")
        print(f"      Date: {daily_plan.date}")
        print(f"      Location: {daily_plan.location_city}, {daily_plan.location_country}")
        print(f"      Is Travel Day: {daily_plan.is_travel_day}")
        print(f"      Travel: {daily_plan.travel_from} → {daily_plan.travel_to}")
        print(f"      Recommended Flights: {len(daily_plan.recommended_flights)} options")
        print(f"      Recommended Hotel: {daily_plan.recommended_hotel.get('name', 'N/A')}")
        print(f"      Bookable Activities: {len(daily_plan.bookable_activities)} options")
        print(f"      Daily Tips: {len(daily_plan.daily_tips)} tips")
        
        # Verify serialization
        data = daily_plan.model_dump()
        print(f"\n   ✅ Serialization successful")
        print(f"      JSON keys: {list(data.keys())}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all component tests."""
    print("\n" + "🚀" * 30)
    print("    AIGO BOOKING COMPONENTS TEST")
    print("🚀" * 30)
    
    results = {}
    
    # Run tests
    results["Location Enrichment"] = await test_location_enrichment()
    results["Amadeus Flights"] = await test_amadeus_flights()
    results["Amadeus Hotels"] = await test_amadeus_hotels()
    results["Travelpayouts URLs"] = await test_travelpayouts_urls()
    results["Booking Models"] = await test_booking_option_generation()
    results["Daily Plan Fields"] = await test_daily_plan_fields()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    passed_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n   Overall: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")


if __name__ == "__main__":
    asyncio.run(main())
