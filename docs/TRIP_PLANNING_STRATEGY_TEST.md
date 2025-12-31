# Trip Planning Strategy Test Documentation

**Date:** 2025-12-31  
**Purpose:** Focused testing of trip planning feature with MCP tools integration validation + WebSocket tracking + Context retention  
**Test Script:** `scripts/test_trip_planning_strategy.py`

---

## Overview

This test validates the trip planning feature with specific focus on:
1. ✅ Request success
2. ✅ MCP tools integration status
3. ✅ Itinerary completeness
4. ✅ Tool availability verification
5. ✅ **WebSocket progress tracking (NEW)**
6. ✅ **Context retention across conversation turns (NEW)**

Based on analysis showing tool integration issues and need for real-time tracking and context preservation.

---

## Quick Start

### Prerequisites

1. **Server must be running:**
   ```bash
   cd /home/runner/work/aigo-backend/aigo-backend
   poetry run uvicorn app.main:app --reload
   ```

2. **Required environment variables in `.env`:**
   ```bash
   # OpenAI (Required)
   OPENAI_API_KEY=your_key_here
   
   # Weather API (Optional - fallback available)
   WEATHER_API_KEY=your_key_here
   WEATHER_API_BASE_URL=https://api.openweathermap.org/data/2.5
   
   # Amadeus API (Optional - fallback available)
   AMADEUS_API_KEY=your_key_here
   AMADEUS_API_SECRET=your_secret_here
   
   # Google Maps (Optional - fallback available)
   GOOGLE_MAPS_API_KEY=your_key_here
   ```

3. **Optional: WebSocket support (for real-time tracking test)**
   ```bash
   pip install websockets
   ```
   *Note: If not installed, WebSocket tests will be skipped gracefully.*

### Run the Test

```bash
python scripts/test_trip_planning_strategy.py
```

---

## What Gets Tested

### 1. Server Availability ✅

Verifies that the backend server is running and accessible.

**Success Criteria:**
- Server responds to health check endpoint
- Status code 200
- Health status is "ok"

### 2. Trip Generation Request ✅

Tests the trip planning request with a Bangkok 5-day trip.

**Test Prompt:**
```
วางแผนเที่ยวกรุงเทพ 5 วัน 4 คืน จาก [14 days from today] ถึง [18 days from today]
งบประมาณ 25,000 บาท
สนใจ: วัฒนธรรม, อาหาร, ช้อปปิ้ง
ประเภท: คู่รัก
ต้องการข้อมูลสภาพอากาศและรูปภาพสถานที่ด้วย
```

**Success Criteria:**
- Request returns 200 status
- Response includes `itinerary_id`
- Response includes `task_id`
- Intent classified correctly

### 3. Task Completion Tracking ✅

Monitors the async task until completion.

**Success Criteria:**
- Task status updates properly
- Task completes within 120 seconds
- Final status is "completed" (not "failed")
- Progress updates from 0% to 100%

### 3a. WebSocket Progress Tracking 🌐 (NEW)

Tests real-time progress tracking via WebSocket connection.

**What it tests:**
- WebSocket connection establishment
- Real-time progress messages
- Message format and content
- Connection stability

**Success Criteria:**
- WebSocket connects successfully to `/api/v1/ws/itinerary/{task_id}`
- Receives progress updates in real-time
- Messages include: progress %, status, step, message
- Connection closes properly on completion

**Note:** This test is optional and will be skipped if:
- `websockets` library is not installed
- WebSocket endpoint is not available
- This is acceptable for development environments

### 4. Context Retention Test 🧠 (NEW)

Tests multi-turn conversation context preservation.

**Test Flow:**
1. **Turn 1:** Vague request ("อยากไปเที่ยวทะเล อากาศดีๆ")
2. **Turn 2:** Add details ("งบ 20,000 บาท ไป 3 วัน อยากไปภูเก็ต")
3. **Turn 3:** Confirm dates and generate itinerary

**What it validates:**
- Context from Turn 1 retained in Turn 2
- All context (destination, budget, duration) used in final itinerary
- Conversation flow is natural
- No information loss between turns

**Success Criteria:**
- Final itinerary includes:
  - ✅ Destination: Phuket (from Turn 2)
  - ✅ Budget: 15,000-25,000 THB (from Turn 2)
  - ✅ Duration: 3 days (from Turn 2)
  - ✅ Beach/good weather preference (from Turn 1)

### 5. MCP Tools Integration Validation 🔧

Analyzes the generated itinerary to determine which tools were used.

#### Tools Checked:

**a) WeatherTool**
- ✅ **Active:** Weather context data present in itinerary
- ⚠️ **Missing:** No weather data found
- **Checks:** `itinerary.weather_context` field

**b) AmadeusTool**
- ✅ **Active:** Flight and/or hotel options present
- ⚠️ **Limited:** Partial data or fallback used
- **Checks:** `itinerary.booking_options` with type "flight" or "hotel"

**c) GoogleMapsTransitTool**
- ✅ **Active:** Transit data present in activities
- ⚠️ **Missing:** No transit information
- **Checks:** `activity.transit_to` fields in daily plans

**d) GoogleImageSearch**
- ✅ **Active:** Images present for attractions
- ⚠️ **Missing:** No images found
- **Checks:** `activity.image_url` fields in activities

**e) TravelpayoutsTool**
- ✅ **Active:** Affiliate links present
- ⚠️ **Limited:** No affiliate links found
- **Checks:** `activity.affiliate_url` fields

**f) FallbackSystem**
- ℹ️ **Used:** AI-generated data when APIs unavailable
- **Checks:** `itinerary.metadata.fallback_used` flag

### 6. Itinerary Completeness Validation 📋

Measures the completeness of the generated itinerary.

**Metrics:**

| Metric | Weight | Check |
|--------|--------|-------|
| Has daily plans | 25 pts | At least 1 day planned |
| All days planned | 25 pts | 5/5 days as requested |
| Has activities | 25 pts | Activities scheduled |
| Has weather data | 15 pts | Weather context present |
| Has budget | 10 pts | Budget information set |

**Completeness Score:** 0-100 points

**Success Criteria:**
- Score ≥ 50: Acceptable
- Score ≥ 75: Good
- Score = 100: Excellent

---

## Test Output Example

```
================================================================================
🚀 Starting Trip Planning Strategy Test Suite
================================================================================

================================================================================
🔍 STEP 1: Checking Server Availability
================================================================================
✅ Server is running at http://localhost:8000
   Status: ok

================================================================================
🧪 STEP 2: Testing Trip Generation Request
================================================================================

📝 Test Prompt:
   วางแผนเที่ยวกรุงเทพ 5 วัน 4 คืน จาก 2025-01-14 ถึง 2025-01-18
   งบประมาณ 25,000 บาท
   สนใจ: วัฒนธรรม, อาหาร, ช้อปปิ้ง
   ประเภท: คู่รัก
   ต้องการข้อมูลสภาพอากาศและรูปภาพสถานที่ด้วย

📊 Response Status: 200
✅ Request successful!

📄 Response Data:
   Intent: trip_generation
   Itinerary ID: abc123
   Task ID: task_xyz789

================================================================================
🔧 STEP 3: Validating MCP Tools Integration
================================================================================

💡 Testing WebSocket progress tracking (optional feature)...

================================================================================
🌐 STEP 3a: Testing WebSocket Progress Tracking
================================================================================

🔌 Connecting to WebSocket: ws://localhost:8000/api/v1/ws/itinerary/task_xyz789
✅ WebSocket connected successfully
   📊 [10%] processing - intent_extraction: Understanding your travel request...
   📊 [25%] processing - data_gathering: Gathering weather and travel data...
   📊 [50%] processing - itinerary_generation: Creating your itinerary...
   📊 [75%] processing - monetization: Adding booking options...
   📊 [100%] completed - finalization: Itinerary complete!

✅ Task completed

⏳ Waiting for task completion...
   [0s] Status: processing | Progress: 10%
   [10s] Status: processing | Progress: 40%
   [20s] Status: processing | Progress: 75%

✅ Task completed in 25 seconds

🔍 Analyzing Tool Usage:
   ✅ WeatherTool: Active (data present)
   ⚠️  AmadeusTool: Limited (fallback used)
   ✅ GoogleMapsTransitTool: Active (transit data present)
   ✅ GoogleImageSearch: Active (images present)
   ⚠️  TravelpayoutsTool: No affiliate links
   ℹ️  FallbackSystem: Used for missing data

================================================================================
📋 STEP 4: Validating Itinerary Completeness
================================================================================

📅 Daily Plans: 5/5 days
🎯 Activities: 23 total
🌤️  Weather: ✅ Present
💰 Budget: ✅ Present

📊 Completeness Score: 100/100

💡 Testing context retention (optional feature)...

================================================================================
🧠 STEP 4: Testing Context Retention
================================================================================

📝 Starting multi-turn conversation test...

   Turn 1: Vague request
   User: อยากไปเที่ยวทะเล อากาศดีๆ
   AI: สนใจไปเที่ยวทะเลในช่วงไหนครับ และมีงบประมาณเท่าไหร่...

   Turn 2: Adding details (testing context)
   User: งบ 20,000 บาท ไป 3 วัน อยากไปภูเก็ต
   AI: เข้าใจครับ ภูเก็ต 3 วัน งบ 20,000 บาท ต้องการให้วางแผนเที่ยวให้เลยไหม...

   Turn 3: Confirming dates (should generate itinerary)
   User: ไปวันที่ 2025-01-14 ถึง 2025-01-16
   ✅ Itinerary generation initiated
      Itinerary ID: xyz456
      Task ID: task_abc123

   ⏳ Waiting for itinerary generation...

   🔍 Verifying context retention:
      Destination: Phuket ✅
      Budget: 20000 THB ✅
      Duration: 3 days ✅

   ✅ Context fully retained across 3 turns!

================================================================================
📊 TEST REPORT: Trip Planning Strategy Validation
================================================================================

1️⃣  Server Availability:
   ✅ PASS

2️⃣  Trip Generation Request:
   ✅ PASS

3️⃣  Task Completion:
   ✅ PASS

4️⃣  MCP Tools Integration:
   ✅ WeatherTool: active
   ⚠️  AmadeusTool: limited
   ✅ GoogleMapsTransitTool: active
   ✅ GoogleImageSearch: active
   ⚠️  TravelpayoutsTool: limited
   ℹ️  FallbackSystem: active

5️⃣  Itinerary Completeness:
   Score: 100/100
   Days: 5/5
   Activities: 23

6️⃣  WebSocket Progress Tracking:
   ✅ PASS - WebSocket connection and tracking working

7️⃣  Context Retention:
   ✅ PASS - Context fully retained across conversation turns

================================================================================
✅ OVERALL: PASS

The trip planning feature is working correctly.
Request was successful and task completed.
✅ Context retention is working as expected.
✅ WebSocket progress tracking is functional.
================================================================================
✅ OVERALL: PASS

The trip planning feature is working correctly.
Request was successful and task completed.
================================================================================

💾 Results saved to: test_results_strategy.json
```

---

## Interpreting Results

### ✅ PASS - All Systems Operational

**Conditions:**
- Server available
- Request successful (200)
- Task completed (not failed)
- Itinerary generated

**Meaning:** Core trip planning feature is working correctly.

### ⚠️ PASS with Warnings - Functional with Limitations

**Conditions:**
- Core features working
- Some MCP tools showing "limited" or "missing" status
- Completeness score 50-99

**Meaning:** Feature works but some integrations may need attention.
- Missing API keys → Fallback system activated (expected behavior)
- Limited data → Some external APIs may be unavailable

### ❌ FAIL - Critical Issues

**Conditions:**
- Server unavailable
- Request failed
- Task failed
- No itinerary generated

**Meaning:** Core functionality broken, requires immediate attention.

---

## Tool Integration Status Guide

### Status Types:

1. **✅ active:** Tool is working and providing data
2. **⚠️ limited:** Tool partially working or using fallback
3. **❌ missing:** Tool not providing any data
4. **❓ not_checked:** Tool status not determined

### Common Scenarios:

#### Scenario 1: All Tools Active ✅
```
✅ WeatherTool: active
✅ AmadeusTool: active
✅ GoogleMapsTransitTool: active
✅ GoogleImageSearch: active
✅ TravelpayoutsTool: active
```
**Result:** Perfect! All integrations working.

#### Scenario 2: Fallback Mode ⚠️
```
⚠️  WeatherTool: missing (API key not configured)
⚠️  AmadeusTool: limited (using AI fallback)
✅ GoogleMapsTransitTool: active
✅ GoogleImageSearch: active
⚠️  TravelpayoutsTool: limited
ℹ️  FallbackSystem: Used for missing data
```
**Result:** Acceptable. System using AI-generated data where APIs unavailable.

#### Scenario 3: Critical Failure ❌
```
❌ All tools: not_checked
```
**Result:** Task failed or didn't complete. Check logs.

---

## Troubleshooting

### Issue: Server Not Available

**Symptom:**
```
❌ Server is not accessible: Connection refused
```

**Solution:**
```bash
# Start the server
poetry run uvicorn app.main:app --reload

# Verify it's running
curl http://localhost:8000/api/v1/health
```

### Issue: Task Timeout

**Symptom:**
```
⏰ Timeout waiting for task completion
```

**Causes:**
- OpenAI API slow to respond
- Complex itinerary taking long to generate
- Network issues

**Solution:**
- Check OpenAI API status
- Verify OPENAI_API_KEY is set
- Check internet connectivity
- Try again with simpler prompt

### Issue: Request Failed

**Symptom:**
```
❌ Request failed with status 422
```

**Causes:**
- Invalid prompt format
- Missing required fields
- Server configuration issue

**Solution:**
- Check error message in response
- Verify prompt includes destination and dates
- Check server logs: `poetry run uvicorn app.main:app --reload --log-level debug`

### Issue: All Tools Showing "missing"

**Symptom:**
```
⚠️  All tools showing missing or limited status
```

**Causes:**
- API keys not configured
- .env file not loaded
- APIs quota exceeded

**Solution:**
- Check `.env` file exists and has valid keys
- Verify environment variables loaded: `echo $OPENAI_API_KEY`
- Check API quota/billing status
- Fallback system should still work (acceptable behavior)

---

## Test Results File

Results are saved to: `test_results_strategy.json`

**Structure:**
```json
{
  "server_available": true,
  "request_success": true,
  "task_completion": true,
  "mcp_tools_status": {
    "WeatherTool": {
      "available": true,
      "status": "active"
    },
    "AmadeusTool": {
      "available": false,
      "status": "limited"
    }
  },
  "itinerary_completeness": {
    "has_daily_plans": true,
    "days_planned": 5,
    "expected_days": 5,
    "has_activities": true,
    "total_activities": 23,
    "has_weather": true,
    "has_budget": true,
    "completeness_score": 100.0
  },
  "overall_pass": true
}
```

---

## Custom Test Prompts

You can modify the test prompt in the script to test different scenarios:

### Example 1: International Trip
```python
prompt = """Plan a 7-day trip to Tokyo, Japan from 2025-05-01 to 2025-05-07
Budget: $2,500 USD
Interests: Technology, anime culture, food
Type: Solo traveler
Include weather and photos"""
```

### Example 2: Weekend Getaway
```python
prompt = """วางแผนเที่ยวเชียงใหม่ 3 วัน 2 คืน
งบ 10,000 บาท
สนใจ: ธรรมชาติ, วัด, คาเฟ่
ต้องการข้อมูลอากาศ"""
```

### Example 3: Group Trip
```python
prompt = """Plan a 5-day Phuket trip for 4 people
Budget: 60,000 THB total
Interests: Beaches, water sports, nightlife
Include weather forecasts"""
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Trip Planning Strategy Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      
      - name: Start server
        run: |
          poetry run uvicorn app.main:app &
          sleep 10
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Run strategy test
        run: |
          poetry run python scripts/test_trip_planning_strategy.py
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test_results_strategy.json
```

---

## Next Steps

After running this test:

1. ✅ **If all pass:** Feature is ready for production
2. ⚠️ **If warnings:** Review tool integration status
   - Add missing API keys if needed
   - Verify fallback behavior is acceptable
3. ❌ **If failures:** Debug and fix issues
   - Check server logs
   - Verify configuration
   - Test individual components

---

## Related Documentation

- [COMPREHENSIVE_TEST_PROMPTS.md](./COMPREHENSIVE_TEST_PROMPTS.md) - Full test scenarios
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - General testing guide
- [WEATHER_API.md](./WEATHER_API.md) - Weather API documentation
- [README.md](../README.md) - Project overview

---

## Support

For issues or questions:
1. Check this documentation
2. Review test output and `test_results_strategy.json`
3. Check server logs for detailed errors
4. Verify API keys and configuration

---

**Last Updated:** 2025-12-31  
**Version:** 1.0.0  
**Status:** ✅ Ready for use
