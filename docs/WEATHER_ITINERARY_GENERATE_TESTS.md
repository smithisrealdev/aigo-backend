# Weather API Integration Test for /api/v1/itineraries/generate

## Overview

This document describes comprehensive testing for the `/api/v1/itineraries/generate` endpoint with Weather API integration.

## Test Script

**File:** `scripts/test_itinerary_generate_weather.py`

**Usage:**
```bash
# Start the server first
poetry run uvicorn app.main:app --reload

# Run tests (in another terminal)
python scripts/test_itinerary_generate_weather.py
```

## Test Cases

### Category 1: Weather Inquiry (ถามเกี่ยวสภาพอากาศ)

Tests for general weather-related questions that should return conversational responses.

#### Test 1.1: Current Weather Question (Thai)
**Prompt:** "อากาศที่กรุงเทพตอนนี้เป็นอย่างไรบ้าง"  
**Expected Intent:** `general_inquiry`  
**Expected Behavior:**
- Returns `ConversationalResponse`
- Response should include current weather information
- May include temperature, conditions, humidity
- Should be in Thai language

**Example Response:**
```json
{
  "intent": "general_inquiry",
  "message": "อากาศที่กรุงเทพในตอนนี้มีอุณหภูมิประมาณ 32°C ท้องฟ้าแจ่มใส ความชื้น 70% เหมาะสำหรับกิจกรรมกลางแจ้ง แนะนำให้ใส่เสื้อผ้าระบายอากาศและดื่มน้ำเยอะๆ นะคะ",
  "suggestions": [
    "ดูแผนการเที่ยวกรุงเทพ",
    "แนะนำกิจกรรมกลางแจ้ง"
  ],
  "sources": ["OpenWeatherMap"]
}
```

#### Test 1.2: Weather Forecast Question (English)
**Prompt:** "What's the weather like in Tokyo in April?"  
**Expected Intent:** `general_inquiry`  
**Expected Behavior:**
- Returns forecast information for April
- Includes temperature range
- Mentions typical weather patterns
- English language response

**Example Response:**
```json
{
  "intent": "general_inquiry",
  "message": "In April, Tokyo typically experiences pleasant spring weather with temperatures ranging from 8°C to 18°C. It's mostly sunny with occasional rain. This is cherry blossom season, making it a popular time to visit. Pack layers and bring an umbrella for sudden showers.",
  "suggestions": [
    "Plan a Tokyo itinerary",
    "Best cherry blossom spots"
  ]
}
```

#### Test 1.3: Weather with Trip Planning
**Prompt:** "อากาศที่โตเกียวช่วงเดือนเมษายนเป็นยังไง ควรไปเที่ยวไหม"  
**Expected Intent:** `general_inquiry` or `decision_support`  
**Expected Behavior:**
- Provides weather information
- Gives travel recommendation
- May include pros/cons
- Activity suggestions based on weather

### Category 2: Weather Forecast for Re-planning (พยากรณ์สภาพอากาศสำหรับทำ re-plan)

Tests for scenarios where users want to adjust plans based on weather forecasts.

#### Test 2.1: Check Weather Before Finalizing Plan
**Prompt:** "ฉันกำลังจะไปกรุงเทพสัปดาห์หน้า ช่วยดูสภาพอากาศให้หน่อย แล้วแนะนำว่าควรไปไหนดี"  
**Expected Intent:** `general_inquiry` or `decision_support`  
**Expected Behavior:**
- Fetches 7-day forecast for Bangkok
- Provides weather summary
- Suggests activities based on forecast
- Recommends what to pack

**Example Response:**
```json
{
  "intent": "decision_support",
  "message": "สัปดาห์หน้าที่กรุงเทพจะมีอุณหภูมิ 25-33°C โอกาสฝนตก 30% ในช่วงบ่าย แนะนำกิจกรรม:\n- เช้า: เที่ยววัดและพระราชวัง (อากาศยังไม่ร้อนมาก)\n- กลางวัน: ช้อปปิ้งห้างสรรพสินค้า (หลบร้อน)\n- เย็น: เดินตลาดนัด ล่องเรือเจ้าพระยา\n\nสิ่งที่ควรเตรียม: ร่ม, แว่นกันแดด, ครีมกันแดด, เสื้อผ้าระบายอากาศ",
  "suggestions": [
    "สร้างแผนการเที่ยว 3 วัน",
    "ดูสถานที่ท่องเที่ยวในร่ม"
  ]
}
```

#### Test 2.2: Weather-based Activity Suggestion
**Prompt:** "ถ้าฝนตกที่เชียงใหม่ ควรทำอะไรดี"  
**Expected Intent:** `decision_support`  
**Expected Behavior:**
- Suggests indoor activities
- Provides alternative plans
- May include rainy day recommendations

**Example Response:**
```json
{
  "intent": "decision_support",
  "message": "ถ้าฝนตกที่เชียงใหม่ แนะนำกิจกรรมในร่ม:\n1. เที่ยวพิพิธภัณฑ์และหอศิลป์\n2. นวดสปาและผ่อนคลาย\n3. ชิมอาหารและคาเฟ่\n4. ช้อปปิ้งห้างและตลาดในร่ม\n5. เวิร์คช็อปหัตถกรรม (ทำร่ม, เครื่องปั้น)\n\nหากฝนหยุด: แวะวัดดอยสุเทพ (วิวสวย หมอกหลังฝน)",
  "suggestions": [
    "ดูพิพิธภัณฑ์เชียงใหม่",
    "แนะนำสปาดีๆ"
  ]
}
```

#### Test 2.3: Adjust Plan Based on Weather (English)
**Prompt:** "I'm going to Phuket next week. If it rains, what indoor activities can I do?"  
**Expected Intent:** `decision_support`  
**Expected Behavior:**
- Checks Phuket forecast
- Lists indoor alternatives
- Provides backup plan options

### Category 3: Weather Integration in Itinerary Creation (create plan ต้องนำ weather มาช่วยออกแบบ itinerary)

Tests for full trip generation where weather data should influence the itinerary.

#### Test 3.1: Trip Planning with Weather Consideration (Thai)
**Prompt:** "วางแผนเที่ยวกรุงเทพ 5 วัน จาก 2025-04-01 ถึง 2025-04-05 งบ 20000 บาท อยากทราบสภาพอากาศด้วย"  
**Expected Intent:** `trip_generation`  
**Expected Behavior:**
- Creates itinerary (async task)
- Returns `TripGenerationResponse` with task_id
- Weather data fetched in background
- Itinerary should consider weather:
  - Indoor activities on rainy days
  - Outdoor activities on sunny days
  - Activity timing based on temperature
  - Packing suggestions included

**Example Response:**
```json
{
  "intent": "trip_generation",
  "itinerary_id": "uuid-here",
  "task_id": "task-uuid",
  "status": "pending",
  "message": "กำลังสร้างแผนการเที่ยวกรุงเทพสำหรับคุณ รวมถึงข้อมูลสภาพอากาศและคำแนะนำ",
  "websocket_url": "/api/v1/ws/itinerary/task-uuid",
  "poll_url": "/api/v1/tasks/task-uuid"
}
```

**Expected Itinerary Output:**
- Day-by-day plan with weather forecast
- Activities scheduled based on weather
- Morning/afternoon/evening breakdown
- Weather-aware recommendations
- Packing list based on 5-day forecast

**Example Generated Itinerary:**
```
Day 1 (April 1) - Clear Sky, 25-33°C
Morning:
- 🏛️ Grand Palace (outdoor, best before noon)
- Weather: Sunny, bring sunscreen and hat

Afternoon:
- 🛍️ MBK Center (indoor, escape midday heat)
- Weather: Hot, 33°C

Evening:
- 🌆 Asiatique Riverfront
- Weather: Pleasant, 28°C

Day 2 (April 2) - Scattered Clouds, 60% Rain
Morning:
- 🙏 Wat Pho (visit early before rain)

Afternoon:
- 🏬 Siam Paragon (indoor, rain expected)
- Weather: Rainy afternoon

Evening:
- 🍜 Street Food Tour (if rain stops)

Packing Suggestions:
- Umbrella (60% rain on Day 2)
- Sunscreen (sunny days)
- Light, breathable clothing
- Hat for sun protection
```

#### Test 3.2: Beach Trip with Weather Check
**Prompt:** "Plan a beach vacation to Phuket from 2025-04-01 to 2025-04-05, budget $1000. Consider weather conditions."  
**Expected Intent:** `trip_generation`  
**Expected Behavior:**
- Creates beach-focused itinerary
- Weather heavily influences beach activities
- Indoor alternatives for rainy days
- Water sport recommendations based on wind/waves
- Best beach times based on weather

**Weather Considerations:**
- Sunny days: Beach activities, water sports
- Cloudy days: Beach walks, photography
- Rainy days: Indoor markets, museums, spas
- Windy days: Kite surfing recommendations

#### Test 3.3: Mountain Trip with Weather Awareness
**Prompt:** "เที่ยวเชียงใหม่ 3 วัน งบ 15000 อยากขึ้นดอย ต้องดูสภาพอากาศด้วยนะ"  
**Expected Intent:** `trip_generation`  
**Expected Behavior:**
- Mountain/hiking focused itinerary
- Weather critical for mountain activities
- Safe hiking conditions considered
- Temperature variations (day/night)
- Visibility forecasts for viewpoints

**Weather Considerations:**
- Clear days: Doi Suthep, viewpoints
- Foggy mornings: Photo opportunities
- Rainy days: No hiking, indoor alternatives
- Cold nights: Packing warm clothes

### Category 4: Additional Essential Cases

#### Test 4.1: Multi-destination Trip
**Prompt:** "Plan a 10-day trip visiting Bangkok, Chiang Mai, and Phuket with weather considerations"  
**Expected Behavior:**
- Weather forecast for all three cities
- Different weather patterns considered
- Regional packing suggestions
- Climate-appropriate activities per location

#### Test 4.2: Seasonal Weather Warnings
**Prompt:** "ไปภูเก็ตช่วงมรสุมเดือนกันยายน"  
**Expected Behavior:**
- Monsoon season warning
- Safety considerations
- Indoor activity emphasis
- Alternative travel date suggestions

#### Test 4.3: Weather-dependent Activities
**Prompt:** "สร้างแผนดูดาวและถ่ายภาพ Milky Way ที่ดอยอินทนนท์"  
**Expected Behavior:**
- Clear sky requirements checked
- Moon phase considered
- Cloud cover forecast
- Best viewing times
- Backup dates if weather unsuitable

## Weather Data Integration Points

### 1. Intent Classification
- Classify weather-related queries
- Distinguish between inquiry and trip planning

### 2. Data Gathering (planner_graph.py)
```python
async def _get_weather_with_fallback(intent: ExtractedIntent) -> dict:
    """Fetch weather forecast for trip dates"""
    tool = WeatherTool.forecast
    result = await tool._arun(
        location=intent.destination_city,
        start_date=intent.start_date.isoformat(),
        end_date=intent.end_date.isoformat(),
        units="metric",
    )
    return {"data": result, "is_estimated": False}
```

### 3. Itinerary Generation
- Weather data passed to LLM
- Activities scheduled based on forecast
- Packing suggestions generated
- Safety warnings included

### 4. Response Formatting
- Weather summary in message
- Daily forecasts in itinerary
- Icons and conditions
- Advisory messages

## Success Criteria

### For Weather Inquiry (Test Category 1):
✅ Returns `ConversationalResponse`  
✅ Includes weather information in message  
✅ Provides relevant suggestions  
✅ Responds in user's language  

### For Weather-based Re-planning (Test Category 2):
✅ Returns `ConversationalResponse` or `decision_support`  
✅ Provides weather-aware recommendations  
✅ Suggests alternative activities  
✅ Includes packing advice  

### For Itinerary Creation (Test Category 3):
✅ Returns `TripGenerationResponse`  
✅ Creates itinerary task successfully  
✅ Weather data fetched in background  
✅ Generated itinerary includes:
- Daily weather forecasts
- Weather-appropriate activities
- Activity timing based on conditions
- Packing suggestions
- Weather advisories

## Running the Tests

### Prerequisites
```bash
# Install dependencies
pip install httpx

# Ensure Weather API key is configured
echo "WEATHER_API_KEY=7137f9d6978ba5a84f8a76174a7fcacc" >> .env
echo "WEATHER_API_BASE_URL=https://api.openweathermap.org/data/2.5" >> .env
```

### Start Server
```bash
cd /home/runner/work/aigo-backend/aigo-backend
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
# Run weather integration tests
python scripts/test_itinerary_generate_weather.py

# Expected output:
# - Test execution for all categories
# - Pass/Fail status for each test
# - Summary with statistics
```

### Check Results
```bash
# View generated itineraries
curl http://localhost:8000/api/v1/itineraries/{itinerary_id}

# Check task status
curl http://localhost:8000/api/v1/tasks/{task_id}

# WebSocket monitoring (if needed)
wscat -c ws://localhost:8000/api/v1/ws/itinerary/{task_id}
```

## Expected Weather API Behavior

### During Intent Classification:
- Detects weather-related keywords
- Extracts location and dates
- Determines if trip planning or inquiry

### During Data Gathering:
```
1. Extract intent → Bangkok, 5 days, Apr 1-5
2. Call WeatherTool.forecast() ← Parallel with flights/hotels
3. Get 5-day forecast from OpenWeatherMap
4. Parse daily forecasts, conditions, temperature
5. Generate packing suggestions
6. Create advisory messages
```

### In Generated Itinerary:
```json
{
  "day": 1,
  "date": "2025-04-01",
  "weather": {
    "condition": "clear sky",
    "temperature_min": 25,
    "temperature_max": 33,
    "precipitation_probability": 0.1,
    "humidity": 70,
    "advisory": "Hot weather - bring water and sunscreen"
  },
  "activities": [
    {
      "time": "morning",
      "activity": "Grand Palace",
      "weather_note": "Best time before noon - cooler temperature"
    }
  ]
}
```

## Troubleshooting

### Issue: Weather data not included in response
**Check:**
1. Weather API key configured in .env
2. OpenWeatherMap API is accessible
3. Location name is valid
4. Date range is within forecast limits (typically 5-7 days)

### Issue: Task fails during generation
**Check:**
1. Task status endpoint: GET /api/v1/tasks/{task_id}
2. Look for weather-related errors in task.error field
3. Check if fallback data is being used

### Issue: Incorrect weather for location
**Check:**
1. Location name parsing in intent extraction
2. Weather API geocoding response
3. Coordinates used for weather query

## Notes

- Weather forecasts are typically available for 5-7 days ahead
- Historical data may be used for dates further out
- Fallback mechanism provides estimated data if API fails
- Weather data is cached for 15-30 minutes for performance
- Real-time weather vs forecast handled differently

---

**Created:** 2025-12-31  
**Status:** Ready for testing  
**API Key:** Configured (7137f9d6978ba5a84f8a76174a7fcacc)  
**Endpoint:** POST /api/v1/itineraries/generate
