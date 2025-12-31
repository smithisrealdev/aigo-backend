#!/usr/bin/env python3
"""Quick E2E test for itinerary generation."""

import asyncio
import time
import httpx


async def quick_test():
    """Run a quick end-to-end test."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Health check
        r = await client.get(f"{base_url}/health")
        print(f"✅ Health: {r.json()}")
        
        # 2. Register user
        email = f"test_quick_{int(time.time())}@example.com"
        r = await client.post(f"{base_url}/api/v1/auth/register", json={
            "email": email, 
            "password": "TestPassword123!", 
            "display_name": "Test"
        })
        print(f"{'✅' if r.status_code in [200, 201] else '❌'} Register: {r.status_code}")
        if r.status_code not in [200, 201]:
            print(r.text[:200])
            return
            
        # 3. Login
        r = await client.post(f"{base_url}/api/v1/auth/login", json={
            "email": email, 
            "password": "TestPassword123!"
        })
        print(f"{'✅' if r.status_code == 200 else '❌'} Login: {r.status_code}")
        if r.status_code != 200:
            print(r.text[:200])
            return
            
        tokens = r.json().get("tokens", {})
        token = tokens.get("access_token")
        print(f"✅ Got token: {bool(token)}")
        
        # 4. Generate itinerary
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(f"{base_url}/api/v1/itineraries/generate", json={
            "prompt": "ไปเที่ยว Bangkok 2 วัน งบ 5000"
        }, headers=headers)
        print(f"{'✅' if r.status_code in [200, 201, 202] else '❌'} Generate: {r.status_code}")
        data = r.json()
        task_id = data.get("task_id")
        itinerary_id = data.get("itinerary_id")
        print(f"📋 Task ID: {task_id}")
        print(f"📋 Itinerary ID: {itinerary_id}")
        
        # 5. Wait for completion (poll)
        print("\n⏳ Waiting for task completion...")
        start_time = time.time()
        for i in range(60):  # 120 seconds max
            await asyncio.sleep(2)
            r = await client.get(f"{base_url}/api/v1/itineraries/tasks/{task_id}", headers=headers)
            status_data = r.json()
            status = status_data.get("status", "unknown")
            elapsed = time.time() - start_time
            print(f"  [{elapsed:.0f}s] Poll {i+1}: {status}")
            
            if status.upper() in ["SUCCESS", "COMPLETED", "FAILURE", "FAILED"]:
                print(f"\n{'✅' if 'SUCCESS' in status.upper() or 'COMPLETED' in status.upper() else '❌'} Final status: {status}")
                
                if status.upper() in ["SUCCESS", "COMPLETED"]:
                    # Get itinerary
                    r = await client.get(f"{base_url}/api/v1/itineraries/{itinerary_id}", headers=headers)
                    itin = r.json()
                    print(f"\n📍 Itinerary Results:")
                    print(f"   Title: {itin.get('title', 'N/A')}")
                    print(f"   Status: {itin.get('status')}")
                    print(f"   Destination: {itin.get('destination')}")
                    print(f"   Total Budget: {itin.get('total_budget')} {itin.get('currency')}")
                    
                    # Count days
                    data_field = itin.get("data", {})
                    if isinstance(data_field, dict):
                        days = len(data_field.get("daily_plans", []))
                        print(f"   Days: {days}")
                        hotels = len(data_field.get("hotel_options", []))
                        print(f"   Hotel Options: {hotels}")
                break
        else:
            print("\n❌ Timeout waiting for task")
            
        print("\n" + "=" * 50)
        print("✅ Quick E2E Test Completed!")


if __name__ == "__main__":
    asyncio.run(quick_test())
