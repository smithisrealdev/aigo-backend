#!/usr/bin/env python3
"""Simple sync API test"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("FULL ITINERARY API TEST")
print("=" * 60)

# 1. Health check
print("\n1. Health check...")
r = requests.get(f"{BASE_URL}/api/v1/health")
print(f"   Status: {r.status_code} - {r.json()}")

# 2. Generate
print("\n2. Submitting generation request...")
data = {"prompt": "วางแผนเที่ยว Tokyo 3 วัน งบ 30000 บาท สนใจวัด อาหาร ช้อปปิ้ง เดินทางจากกรุงเทพ"}
r = requests.post(f"{BASE_URL}/api/v1/itineraries/generate", json=data)
print(f"   Status: {r.status_code}")
result = r.json()
print(f"   Intent: {result.get('intent')}")
print(f"   Itinerary ID: {result.get('itinerary_id')}")
print(f"   Task ID: {result.get('task_id')}")

if result.get('intent') != 'trip_generation':
    print(f"   Message: {result.get('message')}")
    exit(0)

task_id = result.get('task_id')
itinerary_id = result.get('itinerary_id')

# 3. Poll for completion
print("\n3. Polling for completion...")
for i in range(60):  # 3 minutes max
    r = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}")
    status = r.json()
    state = status.get('state', 'UNKNOWN')
    progress = status.get('progress', {}) or {}
    
    if isinstance(progress, int):
        progress = {'progress': progress}
    
    step = progress.get('step', 'N/A') if isinstance(progress, dict) else 'N/A'
    pct = progress.get('progress', 0) if isinstance(progress, dict) else progress
    
    print(f"   [{i*3}s] {state} - {step} ({pct}%)")
    
    if state == 'SUCCESS':
        print("   ✅ Completed!")
        break
    elif state in ['FAILURE', 'REVOKED']:
        print(f"   ❌ Failed: {status.get('error')}")
        exit(1)
    
    time.sleep(3)

# 4. Get itinerary
print("\n4. Fetching itinerary...")
r = requests.get(f"{BASE_URL}/api/v1/itineraries/{itinerary_id}/full")
print(f"   Status: {r.status_code}")

if r.status_code != 200:
    print(f"   Error: {r.text[:500]}")
    exit(1)

itinerary = r.json()
ai = itinerary.get('ai_generated_itinerary', {})

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

# Daily plans
daily_plans = ai.get('daily_plans', [])
print(f"\n📅 Daily Plans: {len(daily_plans)}")
for i, day in enumerate(daily_plans, 1):
    activities = day.get('activities', [])
    print(f"\n   Day {i}: {day.get('title', 'N/A')}")
    print(f"   Activities: {len(activities)}")
    for j, act in enumerate(activities[:2], 1):
        loc = act.get('location', {}) or {}
        print(f"      {j}. {act.get('title', 'N/A')}")
        print(f"         Location: {loc.get('name', 'N/A')}")
        print(f"         Coords: ({loc.get('latitude', 0)}, {loc.get('longitude', 0)})")
        print(f"         Place ID: {loc.get('google_place_id', 'N/A')}")

# Flight options
flights = ai.get('flight_options', [])
print(f"\n✈️  Flights: {len(flights)}")
for f in flights[:2]:
    print(f"   - {f.get('airline', f.get('provider', 'N/A'))}: {f.get('price', 'N/A')} {f.get('currency', 'THB')}")
    print(f"     URL: {(f.get('affiliate_url') or f.get('booking_url', 'N/A'))[:60]}...")

# Hotels
hotels = ai.get('hotel_options', [])
print(f"\n🏨 Hotels: {len(hotels)}")
for h in hotels[:2]:
    print(f"   - {h.get('title', h.get('name', 'N/A'))}: {h.get('price_per_night', 'N/A')}/night")
    print(f"     URL: {(h.get('affiliate_url') or h.get('booking_url', 'N/A'))[:60]}...")

# Summary
print("\n" + "=" * 60)
checks = {
    "Daily plans": len(daily_plans) > 0,
    "Flights": len(flights) > 0,
    "Hotels": len(hotels) > 0,
    "Activities": any(len(d.get('activities', [])) > 0 for d in daily_plans),
    "Place IDs": any(a.get('location', {}).get('google_place_id') for d in daily_plans for a in d.get('activities', [])),
}
print("Summary:")
for k, v in checks.items():
    print(f"   {'✅' if v else '❌'} {k}")

# Save to file
with open('/tmp/itinerary_result.json', 'w') as f:
    json.dump(itinerary, f, ensure_ascii=False, indent=2, default=str)
print(f"\n💾 Saved to /tmp/itinerary_result.json")
