"""Quick test for 3-turn conversation context retention."""
import asyncio
import httpx

async def test_conversation():
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login first
        login = await client.post(f"{base_url}/api/v1/auth/login", json={
            "email": "test_e2e@example.com",
            "password": "TestPassword123!"
        })
        if login.status_code != 200:
            print(f"❌ Login failed: {login.status_code}")
            return
        
        tokens = login.json().get("tokens", {})
        access_token = tokens.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        print("✅ Logged in")
        
        # Test 3-turn conversation
        turns = [
            "อยากไปเที่ยวทะเล อากาศดีๆ",
            "ภูเก็ตน่าสนใจดี อยากไป 3 วัน",  
            "งบประมาณประมาณ 15000 บาท"
        ]
        
        for i, prompt in enumerate(turns, 1):
            print(f"\n📝 Turn {i}: {prompt}")
            response = await client.post(
                f"{base_url}/api/v1/itineraries/generate",
                json={"prompt": prompt},
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                intent = data.get("intent", "N/A")
                msg = data.get("message", "")[:150]
                print(f"   Intent: {intent}")
                print(f"   Response: {msg}...")
            else:
                print(f"   Error: {response.text[:100]}")
        
        print("\n✅ 3-turn conversation test complete")

if __name__ == "__main__":
    asyncio.run(test_conversation())
