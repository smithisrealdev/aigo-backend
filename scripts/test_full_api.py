#!/usr/bin/env python3
"""
Full Itinerary Generation Test via API

Tests the complete flow:
1. Call /generate endpoint
2. Poll for task completion  
3. Get full itinerary data
4. Verify all booking options are present

Run: python3 scripts/test_full_api.py
"""

import asyncio
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE_URL = "http://localhost:8000"


async def test_full_itinerary_api():
    """Test full itinerary generation via API."""
    
    print("\n" + "=" * 70)
    print("🧪 FULL ITINERARY GENERATION API TEST")
    print("=" * 70)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        
        # Step 1: Check server health
        print("\n📡 Step 1: Checking server health...")
        health = await client.get("/api/v1/health")
        if health.status_code != 200:
            print(f"   ❌ Server not healthy: {health.status_code}")
            return
        print(f"   ✅ Server is healthy")
        
        # Step 2: Submit generation request
        print("\n📤 Step 2: Submitting itinerary generation request...")
        start_date = date.today() + timedelta(days=14)
        
        request_data = {
            "prompt": f"วางแผนเที่ยว Tokyo 3 วัน 2 คืน เดินทางจากกรุงเทพ วันที่ {start_date} งบ 30000 บาท สนใจวัด ช้อปปิ้ง อาหาร"
        }
        
        print(f"   Request: {request_data['prompt'][:60]}...")
        
        response = await client.post(
            "/api/v1/itineraries/generate",
            json=request_data
        )
        
        if response.status_code not in [200, 202]:
            print(f"   ❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        result = response.json()
        print(f"   ✅ Request accepted")
        print(f"   Intent: {result.get('intent', 'N/A')}")
        
        # Check if it's a trip generation
        if result.get('intent') != 'trip_generation':
            print(f"   ⚠️  Not a trip generation intent: {result.get('intent')}")
            print(f"   Message: {result.get('message', 'N/A')}")
            return
        
        itinerary_id = result.get('itinerary_id')
        task_id = result.get('task_id')
        poll_url = result.get('poll_url')
        
        print(f"   Itinerary ID: {itinerary_id}")
        print(f"   Task ID: {task_id}")
        print(f"   Poll URL: {poll_url}")
        
        # Step 3: Poll for completion
        print("\n⏳ Step 3: Waiting for generation to complete...")
        max_wait = 180  # 3 minutes
        poll_interval = 3
        elapsed = 0
        
        while elapsed < max_wait:
            status_response = await client.get(f"/api/v1/tasks/{task_id}")
            
            if status_response.status_code != 200:
                print(f"   ⚠️  Poll failed: {status_response.status_code}")
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue
            
            status = status_response.json()
            state = status.get('state', 'UNKNOWN')
            progress = status.get('progress', {})
            
            # Print progress
            step = progress.get('step', 'unknown')
            pct = progress.get('progress', 0)
            msg = progress.get('message', '')
            
            print(f"   [{elapsed}s] {state} - {step} ({pct}%) - {msg[:50]}...")
            
            if state == 'SUCCESS':
                print(f"\n   ✅ Generation completed!")
                break
            elif state in ['FAILURE', 'REVOKED']:
                print(f"\n   ❌ Generation failed: {state}")
                error = status.get('error', 'Unknown error')
                print(f"   Error: {error}")
                return
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        if elapsed >= max_wait:
            print(f"\n   ⚠️  Timeout after {max_wait}s")
            return
        
        # Step 4: Get full itinerary data
        print("\n📥 Step 4: Fetching full itinerary data...")
        
        itinerary_response = await client.get(f"/api/v1/itineraries/{itinerary_id}/full")
        
        if itinerary_response.status_code != 200:
            print(f"   ❌ Failed to get itinerary: {itinerary_response.status_code}")
            print(f"   Response: {itinerary_response.text[:500]}")
            return
        
        itinerary = itinerary_response.json()
        
        # Step 5: Analyze results
        print("\n" + "=" * 70)
        print("📊 RESULTS ANALYSIS")
        print("=" * 70)
        
        # Basic info
        print(f"\n📋 Basic Info:")
        print(f"   Title: {itinerary.get('title', 'N/A')}")
        print(f"   Status: {itinerary.get('status', 'N/A')}")
        print(f"   Budget: {itinerary.get('budget', 'N/A')} {itinerary.get('currency', 'THB')}")
        
        # AI Generated content
        ai_itinerary = itinerary.get('ai_generated_itinerary', {})
        
        # Response
        print(f"\n💬 AI Response:")
        response_text = ai_itinerary.get('response', '')
        print(f"   {response_text[:200]}..." if response_text else "   N/A")
        
        # Daily plans
        daily_plans = ai_itinerary.get('daily_plans', [])
        print(f"\n📅 Daily Plans: {len(daily_plans)} days")
        
        for i, day in enumerate(daily_plans, 1):
            print(f"\n   Day {i}: {day.get('title', 'Untitled')}")
            print(f"      Date: {day.get('date') or day.get('plan_date', 'N/A')}")
            print(f"      Location: {day.get('location_city', 'N/A')}, {day.get('location_country', 'N/A')}")
            print(f"      Is Travel Day: {day.get('is_travel_day', False)}")
            
            # Activities
            activities = day.get('activities', [])
            print(f"      Activities: {len(activities)}")
            for j, act in enumerate(activities[:3], 1):
                title = act.get('title', 'Untitled')
                location = act.get('location', {})
                loc_name = location.get('name', 'N/A') if location else 'N/A'
                place_id = location.get('google_place_id', 'N/A') if location else 'N/A'
                lat = location.get('latitude', 0) if location else 0
                lng = location.get('longitude', 0) if location else 0
                
                print(f"         {j}. {title}")
                print(f"            Location: {loc_name}")
                print(f"            Coords: ({lat}, {lng})")
                print(f"            Place ID: {place_id[:30] if place_id != 'N/A' else 'N/A'}...")
            
            # Recommended flights (travel day)
            rec_flights = day.get('recommended_flights', [])
            if rec_flights:
                print(f"      Recommended Flights: {len(rec_flights)}")
                for f in rec_flights[:1]:
                    print(f"         - {f.get('airline', f.get('provider', 'N/A'))}: {f.get('price', 'N/A')}")
            
            # Recommended hotel
            rec_hotel = day.get('recommended_hotel')
            if rec_hotel:
                print(f"      Recommended Hotel: {rec_hotel.get('title', rec_hotel.get('name', 'N/A'))}")
            
            # Daily tips
            tips = day.get('daily_tips', [])
            if tips:
                print(f"      Daily Tips: {len(tips)}")
                for t in tips[:2]:
                    print(f"         - {t[:60]}...")
        
        # Flight options
        flight_options = ai_itinerary.get('flight_options', [])
        print(f"\n✈️  Flight Options: {len(flight_options)}")
        for i, f in enumerate(flight_options[:3], 1):
            airline = f.get('airline', f.get('provider', 'N/A'))
            price = f.get('price', f.get('total_price', 'N/A'))
            currency = f.get('currency', 'THB')
            booking_url = f.get('affiliate_url', f.get('booking_url', 'N/A'))
            print(f"   {i}. {airline}: {price} {currency}")
            print(f"      Booking: {booking_url[:60] if booking_url != 'N/A' else 'N/A'}...")
        
        # Hotel options
        hotel_options = ai_itinerary.get('hotel_options', [])
        print(f"\n🏨 Hotel Options: {len(hotel_options)}")
        for i, h in enumerate(hotel_options[:3], 1):
            name = h.get('title', h.get('name', 'N/A'))
            price = h.get('price_per_night', h.get('price', 'N/A'))
            currency = h.get('currency', 'JPY')
            booking_url = h.get('affiliate_url', h.get('booking_url', 'N/A'))
            print(f"   {i}. {name}: {price} {currency}/night")
            print(f"      Booking: {booking_url[:60] if booking_url != 'N/A' else 'N/A'}...")
        
        # Activity options
        activity_options = ai_itinerary.get('activities_option', [])
        print(f"\n🎯 Activity Booking Options: {len(activity_options)}")
        for i, a in enumerate(activity_options[:3], 1):
            name = a.get('title', a.get('name', 'N/A'))
            price = a.get('price', 'N/A')
            booking_url = a.get('affiliate_url', a.get('booking_url', 'N/A'))
            print(f"   {i}. {name}: {price} THB")
            print(f"      Booking: {booking_url[:60] if booking_url != 'N/A' else 'N/A'}...")
        
        # Summary
        print("\n" + "=" * 70)
        print("📋 SUMMARY")
        print("=" * 70)
        
        checks = {
            "Has daily plans": len(daily_plans) > 0,
            "Has flight options": len(flight_options) > 0,
            "Has hotel options": len(hotel_options) > 0,
            "Has activities": any(len(d.get('activities', [])) > 0 for d in daily_plans),
            "Activities have titles": all(
                a.get('title') and a.get('title') != 'Activity' 
                for d in daily_plans 
                for a in d.get('activities', [])
            ),
            "Locations have names": any(
                a.get('location', {}).get('name') 
                for d in daily_plans 
                for a in d.get('activities', [])
            ),
            "Locations have place_id": any(
                a.get('location', {}).get('google_place_id') 
                for d in daily_plans 
                for a in d.get('activities', [])
            ),
            "Locations have coordinates": any(
                a.get('location', {}).get('latitude', 0) != 0 
                for d in daily_plans 
                for a in d.get('activities', [])
            ),
            "Flights have booking URL": any(
                f.get('affiliate_url') or f.get('booking_url') 
                for f in flight_options
            ) if flight_options else False,
            "Hotels have booking URL": any(
                h.get('affiliate_url') or h.get('booking_url') 
                for h in hotel_options
            ) if hotel_options else False,
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")
        
        passed = sum(checks.values())
        total = len(checks)
        print(f"\n   Overall: {passed}/{total} checks passed ({passed/total*100:.0f}%)")
        
        if passed == total:
            print("\n🎉 ALL CHECKS PASSED!")
        else:
            print(f"\n⚠️  {total - passed} check(s) failed")
        
        # Save full response to file for inspection
        output_file = Path(__file__).parent / "test_output_itinerary.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(itinerary, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 Full response saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(test_full_itinerary_api())
