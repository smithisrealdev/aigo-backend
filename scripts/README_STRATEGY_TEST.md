# Quick Reference: Trip Planning Strategy Test

## ⚡ Quick Start

```bash
# 1. Start the server
poetry run uvicorn app.main:app --reload

# 2. Run the test (in another terminal)
python scripts/test_trip_planning_strategy.py
```

## 📊 What It Tests

- ✅ Server availability
- ✅ Trip generation request
- ✅ Task completion tracking
- ✅ MCP tools integration status
- ✅ Itinerary completeness

## 🔧 MCP Tools Validated

1. **WeatherTool** - Weather forecasts
2. **AmadeusTool** - Flights & hotels
3. **GoogleMapsTransitTool** - Directions
4. **GoogleImageSearch** - Attraction images
5. **TravelpayoutsTool** - Affiliate links
6. **FallbackSystem** - AI-generated data

## 📋 Expected Output

```
✅ Server is running
✅ Request successful!
✅ Task completed in XX seconds
✅ WeatherTool: active
⚠️  AmadeusTool: limited (fallback used)
✅ GoogleMapsTransitTool: active
✅ GoogleImageSearch: active
⚠️  TravelpayoutsTool: limited
📊 Completeness Score: 100/100
✅ OVERALL: PASS
```

## ⚠️ Common Issues

**Server not running:**
```bash
poetry run uvicorn app.main:app --reload
```

**Missing API keys:**
- Set `OPENAI_API_KEY` in `.env` (required)
- Other API keys optional (fallback available)

**Task timeout:**
- Check OpenAI API status
- Verify API key is valid
- Try again (network issue)

## 📖 Full Documentation

See [docs/TRIP_PLANNING_STRATEGY_TEST.md](../docs/TRIP_PLANNING_STRATEGY_TEST.md) for:
- Detailed test documentation
- Troubleshooting guide
- Custom test prompts
- Integration examples

## 🎯 Success Criteria

**PASS:** Core features working, itinerary generated
**PASS with Warnings:** Working with fallback for missing APIs
**FAIL:** Server down, request failed, or task failed

---

**Pro Tip:** The test saves results to `test_results_strategy.json` for review.
