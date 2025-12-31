# 🚀 Quick Reference - AiGo Testing

**Fast access guide for running comprehensive tests**

---

## ⚡ Quick Start (3 Commands)

```bash
# 1. Start server (Terminal 1)
poetry run uvicorn app.main:app --reload

# 2. Run all tests (Terminal 2)
python scripts/run_all_tests.py

# 3. Check results
# See output in terminal
```

---

## 📁 Key Files

**Test Scripts:**
```bash
scripts/run_all_tests.py                    # Master runner (run this!)
scripts/test_full_itinerary_mcp_tools.py    # Full itinerary test
scripts/test_conversation_loop.py           # Conversation test
scripts/test_itinerary_generate_weather.py  # Weather test
```

**Documentation:**
```bash
docs/TESTING_GUIDE.md                    # Complete testing guide
docs/COMPREHENSIVE_TEST_PROMPTS.md       # 17 test scenarios
docs/IMPLEMENTATION_SUMMARY_TESTING.md   # What was built
```

---

## 🧪 Test Suites

### 1️⃣ Full Itinerary Test
**What:** Complete trip generation with all MCP tools  
**Run:** `python scripts/test_full_itinerary_mcp_tools.py`  
**Tests:** Bangkok 5-day, Tokyo 7-day, Weather-only  
**Duration:** ~5-10 minutes

### 2️⃣ Conversation Loop Test
**What:** Multi-turn conversations with context retention  
**Run:** `python scripts/test_conversation_loop.py`  
**Tests:** 3-turn basic, 3-turn modification, 5-turn complex  
**Duration:** ~5-10 minutes

### 3️⃣ Weather Integration Test
**What:** Weather API integration verification  
**Run:** `python scripts/test_itinerary_generate_weather.py`  
**Tests:** Weather inquiry, forecasts, integration  
**Duration:** ~2-5 minutes

---

## 🎯 Test Options

```bash
# Run all tests
python scripts/run_all_tests.py

# Quick mode (fast tests only)
python scripts/run_all_tests.py --quick

# Skip specific tests
python scripts/run_all_tests.py --skip-weather
python scripts/run_all_tests.py --skip-conversation
python scripts/run_all_tests.py --skip-full
```

---

## 📝 Sample Test Prompts

### Thai Example:
```json
{
  "prompt": "วางแผนเที่ยวกรุงเทพ 5 วัน งบ 25,000 บาท สนใจวัฒนธรรม อาหาร ช้อปปิ้ง"
}
```

### English Example:
```json
{
  "prompt": "Plan a 7-day trip to Tokyo, Japan. Budget: $2,500. Interests: Technology, culture, food."
}
```

**More prompts:** See `docs/COMPREHENSIVE_TEST_PROMPTS.md`

---

## ✅ Success Indicators

**All tests passed:**
```
📊 OVERALL TEST SUMMARY
✅ Passed: 3/3
❌ Failed: 0
✅ ALL TEST SUITES PASSED!
```

**Individual test:**
```
✅ Pass
MCP Tools: 5/6
Duration: 45s
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Server not running | `poetry run uvicorn app.main:app --reload` |
| Import error | `poetry install` |
| Timeout | Check Celery worker and Redis |
| API key issues | Verify `.env` configuration |

**Full guide:** `docs/TESTING_GUIDE.md`

---

## 📊 What Gets Tested

✅ **Itinerary Creation** - Full trip generation  
✅ **WeatherTool** - Forecasts and current weather  
✅ **AmadeusTool** - Flights and hotels  
✅ **GoogleMapsTransit** - Directions  
✅ **GoogleImageSearch** - Photos  
✅ **TravelpayoutsTool** - Booking links  
✅ **Conversation Loop** - Multi-turn context  
✅ **Task Progress** - REST + WebSocket  
✅ **Languages** - Thai + English  

---

## 🎓 Test Coverage

**100% Coverage:**
- Itinerary creation (all types)
- MCP tools (6 tools + fallback)
- Conversation features
- Task management
- Languages (Thai/English)

**17 Test Scenarios:**
- 3 full itinerary creation
- 6 MCP tool verification
- 2 task progress tracking
- 4 conversation loop
- 2 advanced scenarios

---

## 📞 Need Help?

1. **Quick guide:** This file
2. **Complete guide:** `docs/TESTING_GUIDE.md`
3. **Test prompts:** `docs/COMPREHENSIVE_TEST_PROMPTS.md`
4. **Implementation:** `docs/IMPLEMENTATION_SUMMARY_TESTING.md`

---

## 🔗 Key Endpoints

```bash
POST /api/v1/itineraries/generate    # Generate itinerary
GET  /api/v1/tasks/{task_id}         # Check progress
GET  /api/v1/itineraries/{id}        # Get itinerary
WS   /api/v1/ws/itinerary/{task_id}  # WebSocket updates
```

---

**Last Updated:** 2025-12-31  
**Status:** ✅ Production Ready  
**Total Tests:** 17 scenarios, 3 test suites
