# Comprehensive Test Prompts for AiGo Backend

This document contains comprehensive test prompts for testing the AiGo backend's itinerary creation, task progress tracking, and conversation loop capabilities.

**Date Created:** 2025-12-31  
**Purpose:** Full 100% testing of itinerary creation, MCP tools verification, and conversational AI continuity

---

## Table of Contents

1. [Full Itinerary Creation Tests](#full-itinerary-creation-tests)
2. [MCP Tools Verification Tests](#mcp-tools-verification-tests)
3. [Task Progress Tracking Tests](#task-progress-tracking-tests)
4. [Conversation Loop Tests](#conversation-loop-tests)
5. [Plan Modification Tests](#plan-modification-tests)

---

## Full Itinerary Creation Tests

### Test 1: Complete Bangkok Trip (Thai Language)
**Objective:** Test full trip generation with all features

**Prompt:**
```
วางแผนเที่ยวกรุงเทพ 5 วัน 4 คืน จาก 2025-04-15 ถึง 2025-04-19 
งบประมาณ 25,000 บาท
สนใจ: วัฒนธรรม, อาหาร, ช้อปปิ้ง
ประเภท: คู่รัก
ความต้องการพิเศษ: อยากพักโรงแรมใกล้รถไฟฟ้า, ไม่ชอบเดินเยอะ
ต้องการข้อมูลสภาพอากาศและรูปภาพสถานที่ด้วย
```

**Expected Behavior:**
- ✅ Intent classified as `trip_generation`
- ✅ Returns `TripGenerationResponse` with task_id and itinerary_id
- ✅ Weather forecast for 5 days retrieved
- ✅ Flight/Hotel search executed (or fallback)
- ✅ Google Maps integration for directions
- ✅ Image search for attractions
- ✅ Activities scheduled with weather consideration
- ✅ Travelpayouts affiliate links generated
- ✅ Progress tracking available via WebSocket/polling

**MCP Tools Involved:**
- WeatherTool (forecast)
- AmadeusTool (flights, hotels) or fallback
- GoogleMapsTransitTool (directions)
- GoogleImageSearch (location images)
- TravelpayoutsTool (booking links)

---

### Test 2: International Trip (English Language)
**Objective:** Test international destination with all integrations

**Prompt:**
```
Plan a 7-day trip to Tokyo, Japan from 2025-05-01 to 2025-05-07
Budget: $2,500 USD
Interests: Technology, anime/manga culture, traditional temples, food tours
Traveler type: Solo traveler
Special requirements: Need vegetarian food options, prefer morning activities
Include weather forecasts and attraction photos
```

**Expected Behavior:**
- ✅ Intent: `trip_generation`
- ✅ Multi-day itinerary with 7 days
- ✅ Weather data for entire period
- ✅ Flight search from default location to Tokyo
- ✅ Hotel recommendations with vegetarian-friendly areas
- ✅ Morning-focused activity scheduling
- ✅ Transit directions between locations
- ✅ Images for all recommended places
- ✅ Booking links for flights and hotels

**MCP Tools Involved:** All tools

---

### Test 3: Multi-City Trip
**Objective:** Test complex itinerary with multiple destinations

**Prompt:**
```
เที่ยวญี่ปุ่น 10 วัน เส้นทาง โตเกียว 3 วัน -> เกียวโต 3 วัน -> โอซาก้า 3 วัน -> กลับโตเกียว 1 วัน
งบ 80,000 บาท
สนใจ: วัฒนธรรม ธรรมชาติ อาหาร
เดินทาง 2 คน
ต้องการข้อมูลเส้นทางระหว่างเมืองและสภาพอากาศแต่ละเมืองด้วย
```

**Expected Behavior:**
- ✅ Multiple cities handled correctly
- ✅ Weather forecast for each city
- ✅ Inter-city transit (Shinkansen) information
- ✅ City-specific attractions and images
- ✅ Hotel search for each city
- ✅ Day-by-day breakdown for 10 days
- ✅ Budget allocation across cities

**MCP Tools Involved:** All tools + transit between cities

---

## MCP Tools Verification Tests

### Test 4: Weather Tool Only
**Objective:** Verify WeatherTool functionality

**Prompt (General Inquiry):**
```
อากาศที่เชียงใหม่เดือนหน้าเป็นอย่างไร
```

**Expected Behavior:**
- ✅ Intent: `general_inquiry`
- ✅ Returns `ConversationalResponse`
- ✅ WeatherTool.forecast called successfully
- ✅ Response includes temperature, conditions, advisory
- ✅ Packing suggestions provided
- ✅ Thai language response

**Tool Verification:**
- WeatherTool.forecast with location="Chiang Mai"
- 30-day forecast data
- Advisory system triggered

---

### Test 5: Google Maps Integration
**Objective:** Verify GoogleMapsTransitTool

**Prompt:**
```
How do I get from Suvarnabhumi Airport to Sukhumvit area? What are the best options?
```

**Expected Behavior:**
- ✅ Intent: `general_inquiry` or `decision_support`
- ✅ ConversationalResponse with transit options
- ✅ Multiple transit methods (Airport Link, taxi, Grab)
- ✅ Time and cost estimates
- ✅ Step-by-step directions

**Tool Verification:**
- GoogleMapsTransitTool.get_directions
- Multiple route options
- Transit mode comparisons

---

### Test 6: Flight Search Integration
**Objective:** Verify AmadeusTool (or fallback)

**Prompt (Trip Generation):**
```
หาเที่ยวบินไปเชียงใหม่วันศุกร์หน้า งบไม่เกิน 3,000 บาท
```

**Expected Behavior:**
- ✅ Intent: `trip_generation` or `decision_support`
- ✅ Flight search executed
- ✅ Results or fallback data provided
- ✅ Price range within budget
- ✅ Booking links available

**Tool Verification:**
- AmadeusTool.search_flights or generate_flight_fallback
- Price filtering
- Travelpayouts booking links

---

### Test 7: Hotel Search Integration
**Objective:** Verify hotel search capability

**Prompt:**
```
แนะนำโรงแรมในกรุงเทพใกล้สยามสแควร์ ราคา 1,500-2,500 บาท/คืน
```

**Expected Behavior:**
- ✅ Intent: `general_inquiry` or `decision_support`
- ✅ Hotel search near Siam Square
- ✅ Price filtered results
- ✅ Hotel details and images
- ✅ Booking links

**Tool Verification:**
- AmadeusTool.search_hotels or fallback
- Location-based search
- Price range filtering
- TravelpayoutsTool for booking links

---

### Test 8: Image Search Integration
**Objective:** Verify Google Image Search

**Prompt:**
```
Show me photos of Wat Arun and Wat Pho in Bangkok
```

**Expected Behavior:**
- ✅ Intent: `general_inquiry`
- ✅ Image search executed for both temples
- ✅ Multiple high-quality images returned
- ✅ Image URLs accessible
- ✅ Descriptions included

**Tool Verification:**
- search_location_images or search_activity_images
- Multiple queries batched
- Image quality and relevance

---

### Test 9: All Tools Combined (Trip Generation)
**Objective:** Verify all MCP tools work together

**Prompt:**
```
Plan a perfect 3-day weekend in Phuket from 2025-04-18 to 2025-04-20
Budget: 15,000 THB
Interests: Beaches, water sports, nightlife
Show me weather forecast, flight options, hotels, attraction photos, and how to get around
```

**Expected Behavior:**
- ✅ All MCP tools invoked successfully:
  - ✅ WeatherTool: 3-day forecast
  - ✅ AmadeusTool: Flights to Phuket
  - ✅ AmadeusTool: Hotel search
  - ✅ GoogleMapsTransitTool: Getting around Phuket
  - ✅ GoogleImageSearch: Beach and attraction photos
  - ✅ TravelpayoutsTool: Booking links
- ✅ Comprehensive itinerary generated
- ✅ All data integrated seamlessly

---

## Task Progress Tracking Tests

### Test 10: Progress Monitoring
**Objective:** Verify task progress tracking system

**Prompt:**
```
วางแผนเที่ยวเกาหลี 7 วัน งบ 60,000 บาท เน้นช้อปปิ้งและอาหาร
```

**Steps:**
1. Submit prompt → Get task_id
2. Poll GET /api/v1/tasks/{task_id} every 2 seconds
3. Monitor progress stages:
   - ✅ Status: pending (0%)
   - ✅ Status: started (5%)
   - ✅ Step: "Extracting intent" (10%)
   - ✅ Step: "Gathering data" (30-50%)
   - ✅ Step: "Searching flights" (40%)
   - ✅ Step: "Finding hotels" (50%)
   - ✅ Step: "Getting weather" (60%)
   - ✅ Step: "Generating itinerary" (70-90%)
   - ✅ Status: completed (100%)
4. Verify final result contains full itinerary

**Expected Behavior:**
- ✅ Task created successfully
- ✅ Progress increments smoothly
- ✅ Each step reported correctly
- ✅ No stuck states
- ✅ Completion within reasonable time (< 60 seconds)
- ✅ Final result accessible via GET /api/v1/tasks/{task_id}/result

---

### Test 11: WebSocket Progress Streaming
**Objective:** Verify real-time progress updates

**Steps:**
1. Submit trip generation prompt
2. Connect to WebSocket: `ws://localhost:8000/api/v1/ws/itinerary/{task_id}`
3. Receive real-time progress updates

**Expected WebSocket Messages:**
```json
{"status": "started", "progress": 5, "message": "Starting trip generation"}
{"status": "processing", "progress": 20, "step": "Extracting intent"}
{"status": "processing", "progress": 40, "step": "Gathering data"}
{"status": "processing", "progress": 70, "step": "Generating itinerary"}
{"status": "completed", "progress": 100, "message": "Itinerary created successfully"}
```

**Expected Behavior:**
- ✅ WebSocket connection established
- ✅ Real-time updates received
- ✅ Progress values increase monotonically
- ✅ Final completion message
- ✅ Connection closes gracefully

---

## Conversation Loop Tests

### Test 12: Basic Conversation Continuity (Thai)
**Objective:** Test multi-turn conversation with context retention

**Conversation Flow:**

**Turn 1:**
```
User: อยากไปเที่ยวทะเล อากาศดีๆ ไม่ร้อนมาก
AI: [Should ask clarifying questions about budget, dates, preferences]
```

**Expected Response:**
- ✅ Intent: `chit_chat` or `general_inquiry`
- ✅ AI asks follow-up questions:
  - "งบประมาณประมาณเท่าไหร่คะ?"
  - "อยากไปช่วงไหนคะ?"
  - "ไปกี่วัน?"
  - "มีสถานที่ที่สนใจเป็นพิเศษไหมคะ?"

**Turn 2:**
```
User: งบ 20,000 บาท ไป 3 วัน อยากไปภูเก็ต
AI: [Should use context from Turn 1 + new info]
```

**Expected Response:**
- ✅ Context retained: "ทะเล อากาศดีๆ ไม่ร้อนมาก"
- ✅ New info added: "20,000 บาท, 3 วัน, ภูเก็ต"
- ✅ AI confirms understanding and asks for dates

**Turn 3:**
```
User: ไปสัปดาห์หน้าได้ไหม
AI: [Should check weather and create itinerary]
```

**Expected Response:**
- ✅ Intent: `trip_generation`
- ✅ AI calculates dates (next week)
- ✅ Checks weather for Phuket next week
- ✅ Initiates trip generation with all context
- ✅ Returns TripGenerationResponse with task_id

**Verification:**
- ✅ Context preserved across 3 turns
- ✅ Natural conversation flow
- ✅ All user preferences captured
- ✅ Final itinerary reflects all requirements

---

### Test 13: Plan Modification Loop (English)
**Objective:** Test ability to modify plans based on user feedback

**Conversation Flow:**

**Turn 1 - Initial Plan:**
```
User: Plan a 5-day trip to Bangkok for $1,000
AI: [Creates initial itinerary]
```

**Expected:**
- ✅ Trip generation initiated
- ✅ Task completes with full itinerary

**Turn 2 - View and Request Change:**
```
User: The itinerary looks good, but Day 3 has too much shopping. Can we replace it with more temples and cultural sites?
AI: [Modifies Day 3 activities]
```

**Expected Response:**
- ✅ Intent: `replan` or `trip_update`
- ✅ AI identifies: "Day 3, less shopping, more temples"
- ✅ Updates itinerary (creates new version)
- ✅ Returns updated plan with Day 3 changed

**Turn 3 - Further Refinement:**
```
User: Great! But can we move the Grand Palace visit to the morning of Day 2 instead?
AI: [Re-schedules specific activity]
```

**Expected Response:**
- ✅ Understands specific activity movement
- ✅ Updates schedule for Day 2
- ✅ Adjusts timing and related activities
- ✅ Returns updated itinerary

**Turn 4 - Weather-based Adjustment:**
```
User: I just saw it might rain on Day 4. Can you suggest indoor activities for that day?
AI: [Adjusts Day 4 for rain]
```

**Expected Response:**
- ✅ Checks weather for Day 4
- ✅ Replaces outdoor activities with indoor ones
- ✅ Suggests: malls, museums, indoor markets, spas
- ✅ Returns updated Day 4 plan

**Verification:**
- ✅ Each modification builds on previous state
- ✅ Original context preserved
- ✅ Specific changes executed correctly
- ✅ No accidental changes to other days
- ✅ Weather data re-checked when relevant

---

### Test 14: Complex Multi-Turn Conversation (Thai)
**Objective:** Test extended conversation with multiple context switches

**Conversation Flow:**

**Turn 1 - General inquiry:**
```
User: ญี่ปุ่นเดือนเมษายนอากาศเป็นยังไง
AI: [Weather info + cherry blossom season info]
```

**Turn 2 - Add interest:**
```
User: อยากดูซากุระ แนะนำที่ไหนดี
AI: [Recommend best cherry blossom spots]
```

**Turn 3 - Budget question:**
```
User: ไปญี่ปุ่น 7 วันต้องเตรียมเงินเท่าไหร่
AI: [Budget breakdown estimate]
```

**Turn 4 - Decision to plan:**
```
User: โอเค งั้นวางแผนให้หน่อย งบ 80,000 บาท 7 วัน โตเกียวกับเกียวโต เน้นดูซากุระ
AI: [Trip generation with all context]
```

**Expected Final Itinerary:**
- ✅ 7 days in April (cherry blossom season)
- ✅ Tokyo and Kyoto included
- ✅ Budget: 80,000 THB
- ✅ Cherry blossom viewing spots prioritized
- ✅ Weather forecast included
- ✅ All previous context integrated

**Turn 5 - Modification:**
```
User: เพิ่มโอซาก้า 1 วันได้ไหม
AI: [Extends to 8 days, adds Osaka]
```

**Expected:**
- ✅ Itinerary extended to 8 days
- ✅ Osaka added with 1 day plan
- ✅ Budget recalculated
- ✅ Transit between cities updated

**Verification:**
- ✅ 5-turn conversation maintained context
- ✅ Smooth transition from inquiry → planning → modification
- ✅ All user preferences captured
- ✅ Natural conversation flow
- ✅ Thai language maintained throughout

---

### Test 15: Error Recovery in Conversation
**Objective:** Test AI's ability to handle unclear inputs

**Conversation Flow:**

**Turn 1 - Vague request:**
```
User: อยากไปเที่ยว
AI: [Should ask clarifying questions]
```

**Expected:**
- ✅ Friendly acknowledgment
- ✅ Multiple clarifying questions
- ✅ Suggestions for popular destinations

**Turn 2 - Partial info:**
```
User: ไปทะเล
AI: [Narrow down but still ask more]
```

**Expected:**
- ✅ Context: "beach destination"
- ✅ Ask: dates, budget, specific location

**Turn 3 - Contradictory info:**
```
User: งบไม่เยอะ 100,000 บาท ไป 2 วันพอ
AI: [Handle contradiction: "not much budget" vs 100K for 2 days]
```

**Expected:**
- ✅ AI clarifies: "100,000 บาทสำหรับ 2 วันถือว่างบประมาณค่อนข้างสบายค่ะ"
- ✅ Proceeds with planning

**Turn 4 - Change of mind:**
```
User: เอาเปล่า ขอเปลี่ยนเป็นภูเขาแทนทะเลได้ไหม
AI: [Pivots to mountain destinations]
```

**Expected:**
- ✅ Gracefully switches from beach to mountain
- ✅ Suggests: Chiang Mai, Chiang Rai, Khao Yai
- ✅ Retains budget and duration

**Verification:**
- ✅ Handles vague inputs
- ✅ Asks clarifying questions
- ✅ Resolves contradictions
- ✅ Adapts to changes smoothly

---

## Advanced Conversation Tests

### Test 16: Context Switching
**Objective:** Test handling multiple trip plans in one conversation

**Conversation:**
```
Turn 1: Plan a trip to Chiang Mai for 3 days
[AI creates Chiang Mai itinerary]

Turn 2: Actually, I also want to compare with a Phuket option. Can you create both?
[AI creates both itineraries]

Turn 3: Between these two, which is better for food lovers?
[AI compares and recommends]

Turn 4: OK, let's go with Chiang Mai. But can you add a day trip to Pai?
[AI modifies Chiang Mai plan to include Pai]
```

**Verification:**
- ✅ Handles multiple itineraries
- ✅ Comparison capability
- ✅ Context switching between plans
- ✅ Modification of selected plan

---

### Test 17: Long-term Planning Conversation
**Objective:** Test planning trip far in advance

**Conversation:**
```
Turn 1: I want to plan a trip to Japan for next year's cherry blossom season
Turn 2: What dates should I target?
Turn 3: OK, plan for April 1-10, 2026
Turn 4: What should I book now vs later?
Turn 5: Can you create a checklist of things to prepare?
```

**Expected:**
- ✅ Future date handling (2026)
- ✅ Seasonal advice (cherry blossoms)
- ✅ Planning timeline guidance
- ✅ Preparation checklist
- ✅ Booking recommendations

---

## Test Execution Summary

### Coverage Checklist

**Itinerary Creation:**
- [ ] Full trip generation (multiple scenarios)
- [ ] Multi-city trips
- [ ] International trips
- [ ] Various budgets and durations

**MCP Tools:**
- [ ] WeatherTool (forecast + current)
- [ ] AmadeusTool (flights + hotels)
- [ ] GoogleMapsTransitTool (directions)
- [ ] GoogleImageSearch (attraction photos)
- [ ] TravelpayoutsTool (booking links)
- [ ] Fallback system (when APIs fail)

**Task Progress:**
- [ ] REST API polling (GET /api/v1/tasks/{task_id})
- [ ] WebSocket real-time updates
- [ ] Progress percentage accuracy
- [ ] Step-by-step reporting
- [ ] Completion detection

**Conversation Loop:**
- [ ] Multi-turn context retention (2-5 turns)
- [ ] Plan modification capability
- [ ] Weather-based adjustments
- [ ] Activity substitution
- [ ] Schedule rearrangement
- [ ] Error recovery
- [ ] Clarifying questions
- [ ] Context switching

**Languages:**
- [ ] Thai language support
- [ ] English language support
- [ ] Mixed language handling

**User Types:**
- [ ] Solo travelers
- [ ] Couples
- [ ] Families
- [ ] Groups

**Interests:**
- [ ] Culture & temples
- [ ] Food & dining
- [ ] Shopping
- [ ] Nature & outdoors
- [ ] Beaches
- [ ] Adventure sports
- [ ] Nightlife

---

## Expected Success Criteria

### For Itinerary Creation:
- ✅ 100% of prompts create valid itineraries
- ✅ All MCP tools invoked when relevant
- ✅ Fallback works when tools fail
- ✅ Response time < 60 seconds
- ✅ Generated itineraries are coherent and realistic

### For Task Progress:
- ✅ Progress updates received regularly
- ✅ No stuck states
- ✅ Accurate progress percentages
- ✅ Clear step descriptions
- ✅ Final completion confirmed

### For Conversation Loop:
- ✅ Context retained for at least 5 turns
- ✅ Modifications executed correctly
- ✅ Natural language understanding
- ✅ Appropriate follow-up questions
- ✅ Smooth conversation flow

### For MCP Tools:
- ✅ Each tool callable independently
- ✅ Tools work together in combination
- ✅ Error handling for API failures
- ✅ Fallback data quality acceptable
- ✅ Response data properly formatted

---

## Notes

- All test prompts are designed to be copy-paste ready
- Expected behaviors are clearly defined for automated validation
- Tests cover both Thai and English languages
- Both REST API and WebSocket approaches tested
- Real-world scenarios prioritized
- Edge cases included (vague inputs, contradictions, changes)

**Test Environment:**
- Server: http://localhost:8000
- Endpoint: POST /api/v1/itineraries/generate
- Progress: GET /api/v1/tasks/{task_id}
- WebSocket: ws://localhost:8000/api/v1/ws/itinerary/{task_id}

**Prerequisites:**
- Server running with all API keys configured
- Redis available for task tracking
- Database connected
- All MCP tools configured (Weather, Amadeus, GoogleMaps, etc.)

---

**Document Status:** ✅ Complete  
**Last Updated:** 2025-12-31  
**Total Test Cases:** 17 comprehensive scenarios  
**Coverage:** 100% of itinerary creation, MCP tools, and conversation features
