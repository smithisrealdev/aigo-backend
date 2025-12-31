# 📱 AiGo Chat with AI - API Specification

> **Version:** 1.0  
> **Last Updated:** $(date)  
> **Target:** Mobile Team (iOS/Android)

---

## 📌 Overview

AiGo Chat with AI เป็น Conversational AI ที่ช่วยวางแผนการเดินทาง ตอบคำถามทั่วไปเกี่ยวกับการท่องเที่ยว และพูดคุยทั่วไปกับผู้ใช้

### Key Features
- **Intent Classification**: AI จะแยกแยะประเภทของ message อัตโนมัติ
- **Conversation Memory**: จำบทสนทนาได้ตาม `conversation_id`
- **Context-Aware**: รองรับ GPS location, weather, และ itinerary context

---

## 🔐 Authentication

ทุก endpoint ต้องมี **JWT Access Token** ใน Header:

```http
Authorization: Bearer <access_token>
```

### Token Format
- **Type:** Bearer Token (JWT)
- **Header:** `Authorization`
- **Expires:** ตาม config (default 30 minutes)

### Error Responses
| HTTP Status | Description |
|-------------|-------------|
| 401 | Token missing หรือ invalid |
| 403 | Token expired หรือ revoked |

---

## 🌐 Base URL

```
Production: https://api.aigo.app/api/v1
Development: http://localhost:8000/api/v1
```

---

## 📡 Endpoints

### 1. Send Chat Message

ส่งข้อความไปยัง AI Assistant

```
POST /chat/chat
```

#### Request Headers
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| Authorization | string | ✅ | Bearer token |
| Content-Type | string | ✅ | `application/json` |

#### Request Body

```json
{
  "message": "อยากไปโตเกียว 5 วัน งบ 5 หมื่น",
  "conversation_id": "conv-abc123",
  "itinerary_id": "itin-xyz789",
  "current_location": {
    "lat": 35.6762,
    "lng": 139.6503,
    "city": "Tokyo"
  },
  "current_weather": {
    "temp": 22,
    "condition": "sunny",
    "humidity": 65
  },
  "context": {
    "trip_day": 2,
    "current_activity": "lunch"
  }
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| message | string | ✅ | min: 1, max: 2000 chars | ข้อความจากผู้ใช้ |
| conversation_id | string | ❌ | - | ID สำหรับเก็บ memory ถ้าไม่ส่งจะ generate ใหม่ |
| itinerary_id | string | ❌ | - | ID ของ itinerary ที่กำลังดูอยู่ (ถ้ามี) |
| current_location | object | ❌ | - | GPS location ของผู้ใช้ |
| current_weather | object | ❌ | - | ข้อมูลสภาพอากาศปัจจุบัน |
| context | object | ❌ | - | context เพิ่มเติมตามต้องการ |

#### Response (Success)

```json
{
  "success": true,
  "response": "เข้าใจแล้วครับ! จะจัดแผนโตเกียว 5 วัน งบ 50,000 บาทให้เลยนะครับ รอแปปนึงนะ ✨",
  "intent": "planning",
  "confidence": 0.95,
  "conversation_id": "conv-abc123",
  "response_data": {
    "trigger_planning": true,
    "user_prompt": "อยากไปโตเกียว 5 วัน งบ 5 หมื่น"
  },
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| success | boolean | สถานะ success/failure |
| response | string | ข้อความตอบกลับจาก AI |
| intent | string | ประเภท intent ที่ classify ได้ |
| confidence | float | ค่าความมั่นใจ (0.0-1.0) |
| conversation_id | string | ID สำหรับใช้ในการส่งข้อความถัดไป |
| response_data | object | ข้อมูลเพิ่มเติมตาม intent |
| error | string | Error message (null ถ้าสำเร็จ) |

#### Response (Error)

```json
{
  "detail": "Chat processing failed: <error_message>"
}
```

---

### 2. Get Conversation History

ดึงประวัติการสนทนา

```
GET /chat/history/{conversation_id}?limit=10
```

#### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| conversation_id | string | ✅ | ID ของ conversation |

#### Query Parameters
| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| limit | integer | 10 | 1-100 | จำนวน message ที่ต้องการ |

#### Response

```json
{
  "conversation_id": "conv-abc123",
  "messages": [
    {
      "role": "user",
      "content": "อยากไปโตเกียว 5 วัน งบ 5 หมื่น",
      "timestamp": "2024-01-15T10:30:00Z",
      "intent": "planning"
    },
    {
      "role": "assistant",
      "content": "เข้าใจแล้วครับ! จะจัดแผนโตเกียว 5 วัน งบ 50,000 บาทให้เลยนะครับ รอแปปนึงนะ ✨",
      "timestamp": "2024-01-15T10:30:05Z",
      "intent": null
    }
  ],
  "total_messages": 2
}
```

---

### 3. Delete Conversation History

ลบประวัติการสนทนา

```
DELETE /chat/history/{conversation_id}
```

#### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| conversation_id | string | ✅ | ID ของ conversation ที่ต้องการลบ |

#### Response
- **Status:** `204 No Content`
- **Body:** None

---

### 4. Submit Feedback

ส่ง feedback สำหรับ AI response

```
POST /chat/feedback
```

#### Query Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| conversation_id | string | ✅ | ID ของ conversation |
| message_index | integer | ✅ | Index ของ message ที่ต้องการให้ feedback |
| feedback | string | ✅ | `"positive"` หรือ `"negative"` |
| comment | string | ❌ | ความคิดเห็นเพิ่มเติม |

#### Response
- **Status:** `204 No Content`
- **Body:** None

---

## 🎯 Intent Types

AI จะ classify message เป็น 3 ประเภท:

### 1. `planning` - วางแผนทริป

เมื่อผู้ใช้ต้องการสร้าง/แก้ไข itinerary

**ตัวอย่าง Messages:**
| Message | Description |
|---------|-------------|
| "จัดทริปให้หน่อย" | ขอวางแผนทริป |
| "ไปโตเกียว 5 วัน งบ 5 หมื่น" | ระบุรายละเอียดครบ |
| "เปลี่ยนแผนวันที่ 3 ให้หน่อย" | แก้ไข itinerary |
| "แนะนำที่เที่ยวโตเกียวหน่อย" | ขอ recommendation |

**response_data ที่ได้รับ:**
```json
{
  "trigger_planning": true,
  "user_prompt": "ไปโตเกียว 5 วัน งบ 5 หมื่น"
}
```

> ⚠️ **Mobile Action:** เมื่อได้ `trigger_planning: true` ให้เรียก Itinerary Generate API หรือแสดง UI สำหรับสร้าง itinerary

---

### 2. `general_inquiry` - ถามข้อมูลทั่วไป

เมื่อผู้ใช้ถามคำถามเกี่ยวกับการท่องเที่ยว

**ตัวอย่าง Messages:**
| Message | Description |
|---------|-------------|
| "พรุ่งนี้ที่โตเกียวมีเทศกาลอะไรไหม?" | ถามข้อมูล event |
| "เงินเยนเรทตอนนี้เท่าไหร่?" | ถามอัตราแลกเปลี่ยน |
| "ปลั๊กที่ญี่ปุ่นเป็นแบบไหน?" | ถามข้อมูลทั่วไป |
| "Shibuya Sky ต้องจองล่วงหน้ากี่วัน?" | ถามเรื่อง booking |
| "มีร้านราเมงใกล้ๆ ไหม?" | ถามโดยใช้ location |
| "แล้วอากาศเป็นไง?" | Follow-up question |

**response_data:**
```json
null
```

> ✅ **Mobile Action:** แสดง response ตรงๆ ไม่ต้องทำอะไรเพิ่ม

---

### 3. `chit_chat` - คุยเล่นทั่วไป

เมื่อผู้ใช้พูดคุยทั่วไป ขอบคุณ หรือต้องการ emotional support

**ตัวอย่าง Messages:**
| Message | Description |
|---------|-------------|
| "ขอบคุณมากนะ" | ขอบคุณ |
| "วันนี้เหนื่อยจัง" | บ่น/ระบาย |
| "แอปนี้เจ๋งดี" | ชม |
| "สวัสดี" | ทักทาย |

**response_data:**
```json
null
```

> ✅ **Mobile Action:** แสดง response ตรงๆ ไม่ต้องทำอะไรเพิ่ม

---

## 💬 Conversation Memory

### วิธีใช้งาน

1. **เริ่มบทสนทนาใหม่:** ไม่ต้องส่ง `conversation_id`
2. **ต่อบทสนทนา:** ส่ง `conversation_id` ที่ได้จาก response ก่อนหน้า
3. **เริ่มใหม่:** ไม่ส่ง `conversation_id` หรือส่งค่าใหม่

### ตัวอย่าง Flow

```
User: "อยากไปญี่ปุ่น" (ไม่ส่ง conversation_id)
↓
Response: { conversation_id: "conv-123", ... }
↓
User: "โตเกียวดีไหม" (ส่ง conversation_id: "conv-123")
↓
AI จำได้ว่าคุยเรื่องญี่ปุ่นอยู่
↓
User: "แล้วอากาศเป็นไง?" (ส่ง conversation_id: "conv-123")
↓
AI ตอบเรื่องอากาศที่โตเกียว (เพราะจำ context ได้)
```

---

## 📍 Location Context

### เมื่อไหร่ควรส่ง current_location

| Scenario | Send Location? |
|----------|----------------|
| ถาม "มีร้านอาหารใกล้ๆ ไหม?" | ✅ ควรส่ง |
| ถาม "ขึ้นรถไฟไปไหนได้บ้าง?" | ✅ ควรส่ง |
| ถาม "เงินเยนเรทเท่าไหร่?" | ❌ ไม่จำเป็น |
| ถาม "วันนี้เหนื่อยจัง" | ❌ ไม่จำเป็น |

### Format

```json
{
  "current_location": {
    "lat": 35.6762,
    "lng": 139.6503,
    "city": "Tokyo"
  }
}
```

---

## 🌤️ Weather Context

### Format

```json
{
  "current_weather": {
    "temp": 22,
    "condition": "sunny",
    "humidity": 65
  }
}
```

AI จะใช้ข้อมูลนี้เพื่อ:
- แนะนำกิจกรรมที่เหมาะสมกับอากาศ
- เตือนถ้าฝนตก
- แนะนำให้พักผ่อนถ้าร้อนมาก

---

## ⚠️ Error Handling

### HTTP Status Codes

| Status | Description | Action |
|--------|-------------|--------|
| 200 | Success | แสดง response |
| 400 | Bad Request | แสดง error message |
| 401 | Unauthorized | Redirect to login |
| 403 | Forbidden | Refresh token หรือ logout |
| 500 | Server Error | แสดง generic error + retry |

### Error Response Format

```json
{
  "detail": "Error description here"
}
```

---

## 📱 Mobile Implementation Guide

### 1. Chat Screen UI Components

```
┌─────────────────────────────────────┐
│  Chat with AiGo 🤖                  │
├─────────────────────────────────────┤
│                                     │
│  [User Message Bubble]              │
│            "อยากไปโตเกียว 5 วัน"      │
│                                     │
│  [AI Message Bubble]                │
│  "เข้าใจแล้วครับ! จะจัดแผน..."        │
│                                     │
│  [Intent Badge: planning]           │
│                                     │
├─────────────────────────────────────┤
│  [📎] [📍] [     Type message     ] [➤]│
└─────────────────────────────────────┘
```

### 2. State Management

```typescript
interface ChatState {
  conversationId: string | null;
  messages: Message[];
  isLoading: boolean;
  currentItineraryId: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  intent?: 'planning' | 'general_inquiry' | 'chit_chat';
  responseData?: {
    trigger_planning?: boolean;
    user_prompt?: string;
  };
}
```

### 3. Send Message Flow

```typescript
async function sendMessage(message: string) {
  // 1. Add user message to UI immediately
  addMessageToUI({ role: 'user', content: message });
  
  // 2. Show typing indicator
  setIsLoading(true);
  
  // 3. Call API
  const response = await fetch('/api/v1/chat/chat', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      conversation_id: conversationId,
      itinerary_id: currentItineraryId,
      current_location: await getCurrentLocation(),
      current_weather: await getCurrentWeather(),
    }),
  });
  
  // 4. Handle response
  const data = await response.json();
  
  // 5. Save conversation_id for next message
  setConversationId(data.conversation_id);
  
  // 6. Add AI response to UI
  addMessageToUI({
    role: 'assistant',
    content: data.response,
    intent: data.intent,
    responseData: data.response_data,
  });
  
  // 7. Handle trigger_planning
  if (data.response_data?.trigger_planning) {
    // Show "Create Itinerary" button or auto-navigate
    showCreateItineraryPrompt(data.response_data.user_prompt);
  }
  
  setIsLoading(false);
}
```

### 4. Intent Handling

```typescript
function handleIntent(intent: string, responseData: any) {
  switch (intent) {
    case 'planning':
      if (responseData?.trigger_planning) {
        // Option 1: แสดงปุ่ม "สร้างแผนการเดินทาง"
        showPlanningButton(responseData.user_prompt);
        
        // Option 2: Auto navigate to itinerary creation
        // navigateToCreateItinerary(responseData.user_prompt);
      }
      break;
      
    case 'general_inquiry':
      // แค่แสดง response ปกติ
      break;
      
    case 'chit_chat':
      // แค่แสดง response ปกติ
      // อาจแสดง emoji animation ถ้าเป็นการขอบคุณ
      break;
  }
}
```

### 5. Retry Logic

```typescript
async function sendWithRetry(message: string, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await sendMessage(message);
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await delay(1000 * (i + 1)); // Exponential backoff
    }
  }
}
```

---

## 🧪 Testing Examples

### cURL - Send Message

```bash
curl -X POST "http://localhost:8000/api/v1/chat/chat" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "อยากไปโตเกียว 5 วัน งบ 5 หมื่น"
  }'
```

### cURL - Get History

```bash
curl -X GET "http://localhost:8000/api/v1/chat/history/conv-123?limit=10" \
  -H "Authorization: Bearer <token>"
```

### cURL - Delete History

```bash
curl -X DELETE "http://localhost:8000/api/v1/chat/history/conv-123" \
  -H "Authorization: Bearer <token>"
```

---

## � WebSocket - Real-time Progress Tracking

เมื่อสร้าง Itinerary ผ่าน Chat (intent = `planning` และ `trigger_planning: true`) จะได้ `task_id` สำหรับติดตาม progress แบบ real-time ผ่าน WebSocket

### WebSocket Endpoint

```
WS /api/v1/ws/itinerary/{task_id}
```

**URL Examples:**
```
Production: wss://api.aigo.app/api/v1/ws/itinerary/{task_id}
Development: ws://localhost:8000/api/v1/ws/itinerary/{task_id}
```

---

### Complete Flow

```
1. POST /api/v1/itineraries/generate
   ↓
2. Response: { task_id, websocket_url: "/api/v1/ws/itinerary/{task_id}" }
   ↓
3. Connect WebSocket: ws://host/api/v1/ws/itinerary/{task_id}
   ↓
4. Receive: connected → progress → progress → ... → completed/failed
   ↓
5. Close WebSocket
```

---

### Message Types

| Type | เมื่อไหร่ | Action |
|------|----------|--------|
| `connected` | เชื่อมต่อสำเร็จ | แสดง progress bar, อาจมี current status แล้ว |
| `progress` | task กำลังทำงาน | อัพเดท UI (progress %, step, message) |
| `completed` | สำเร็จ | ปิด progress, โหลด itinerary ที่สร้างเสร็จ |
| `failed` | ล้มเหลว | แสดง error, เช็ค `can_retry` |
| `ping` | keep-alive (ทุก 15 วิ) | ไม่ต้องทำอะไร (optional: update heartbeat) |
| `error` | connection error | แสดง error, retry connection |

---

### Message Formats

#### 1. `connected`
```json
{
  "type": "connected",
  "data": {
    "task_id": "abc-123",
    "status": "pending",
    "progress": 0,
    "message": "Waiting for task to start..."
  },
  "message": "Connected to task progress stream",
  "timestamp": "2026-01-01T10:00:00Z"
}
```

#### 2. `progress`
```json
{
  "type": "progress",
  "data": {
    "task_id": "abc-123",
    "status": "progress",
    "step": "searching_flights",
    "progress": 35,
    "message": "กำลังค้นหาเที่ยวบินที่ดีที่สุด..."
  },
  "timestamp": "2026-01-01T10:00:05Z"
}
```

**Progress Steps:**
| Step | Progress % | Description |
|------|-----------|-------------|
| `started` | 0-5 | เริ่มต้น |
| `analyzing_prompt` | 5-15 | วิเคราะห์ความต้องการ |
| `searching_flights` | 15-35 | ค้นหาเที่ยวบิน |
| `searching_hotels` | 35-50 | ค้นหาโรงแรม |
| `planning_activities` | 50-75 | วางแผนกิจกรรม |
| `optimizing` | 75-90 | ปรับแต่งแผน |
| `finalizing` | 90-100 | สรุปผล |

#### 3. `completed`
```json
{
  "type": "completed",
  "data": {
    "task_id": "abc-123",
    "status": "completed",
    "progress": 100,
    "itinerary_id": "itin-xyz",
    "message": "สร้างแผนการเดินทางเสร็จแล้ว!"
  },
  "has_fallback_data": false,
  "api_errors": [],
  "timestamp": "2026-01-01T10:01:00Z"
}
```

#### 4. `failed`
```json
{
  "type": "failed",
  "data": {
    "task_id": "abc-123",
    "status": "failed",
    "error": "API rate limit exceeded"
  },
  "error": "API rate limit exceeded",
  "error_type": "rate_limit",
  "can_retry": true,
  "retry_after": 60,
  "api_errors": ["flight_api_timeout"],
  "has_fallback_data": false,
  "message": "Task failed",
  "timestamp": "2026-01-01T10:00:30Z"
}
```

#### 5. `ping`
```json
{
  "type": "ping",
  "data": {
    "task_id": "abc-123",
    "status": "progress",
    "progress": 45
  },
  "timestamp": "2026-01-01T10:00:15Z"
}
```

---

### Mobile Implementation - Swift (iOS)

```swift
import Foundation

class ItineraryProgressManager: NSObject, URLSessionWebSocketDelegate {
    private var webSocket: URLSessionWebSocketTask?
    weak var delegate: ItineraryProgressDelegate?
    
    func connect(taskId: String) {
        let url = URL(string: "wss://api.aigo.app/api/v1/ws/itinerary/\(taskId)")!
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        receiveMessage()
    }
    
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleMessage(text)
                default:
                    break
                }
                self?.receiveMessage() // Continue listening
                
            case .failure(let error):
                self?.delegate?.onError(error)
            }
        }
    }
    
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }
        
        DispatchQueue.main.async { [weak self] in
            switch type {
            case "connected":
                self?.delegate?.onConnected(json["data"] as? [String: Any])
                
            case "progress":
                if let progressData = json["data"] as? [String: Any],
                   let progress = progressData["progress"] as? Int,
                   let step = progressData["step"] as? String,
                   let message = progressData["message"] as? String {
                    self?.delegate?.onProgress(progress: progress, step: step, message: message)
                }
                
            case "completed":
                if let completedData = json["data"] as? [String: Any],
                   let itineraryId = completedData["itinerary_id"] as? String {
                    self?.delegate?.onCompleted(itineraryId: itineraryId)
                }
                self?.disconnect()
                
            case "failed":
                let error = json["error"] as? String ?? "Unknown error"
                let canRetry = json["can_retry"] as? Bool ?? false
                let retryAfter = json["retry_after"] as? Int
                self?.delegate?.onFailed(error: error, canRetry: canRetry, retryAfter: retryAfter)
                self?.disconnect()
                
            case "ping":
                break // Optional: update heartbeat
                
            default:
                break
            }
        }
    }
    
    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
    }
}

protocol ItineraryProgressDelegate: AnyObject {
    func onConnected(_ data: [String: Any]?)
    func onProgress(progress: Int, step: String, message: String)
    func onCompleted(itineraryId: String)
    func onFailed(error: String, canRetry: Bool, retryAfter: Int?)
    func onError(_ error: Error)
}
```

---

### Mobile Implementation - Kotlin (Android)

```kotlin
import okhttp3.*
import org.json.JSONObject

class ItineraryProgressManager(
    private val listener: ProgressListener
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient()
    
    fun connect(taskId: String) {
        val request = Request.Builder()
            .url("wss://api.aigo.app/api/v1/ws/itinerary/$taskId")
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                listener.onError(t.message ?: "Connection failed")
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                listener.onDisconnected()
            }
        })
    }
    
    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.getString("type")
            
            when (type) {
                "connected" -> {
                    val data = json.optJSONObject("data")
                    listener.onConnected(data)
                }
                
                "progress" -> {
                    val data = json.getJSONObject("data")
                    listener.onProgress(
                        progress = data.getInt("progress"),
                        step = data.getString("step"),
                        message = data.getString("message")
                    )
                }
                
                "completed" -> {
                    val data = json.getJSONObject("data")
                    val itineraryId = data.getString("itinerary_id")
                    listener.onCompleted(itineraryId)
                    disconnect()
                }
                
                "failed" -> {
                    val error = json.optString("error", "Unknown error")
                    val canRetry = json.optBoolean("can_retry", false)
                    val retryAfter = json.optInt("retry_after", -1)
                    listener.onFailed(error, canRetry, retryAfter.takeIf { it > 0 })
                    disconnect()
                }
                
                "ping" -> {
                    // Optional: update heartbeat
                }
            }
        } catch (e: Exception) {
            listener.onError("Parse error: ${e.message}")
        }
    }
    
    fun disconnect() {
        webSocket?.close(1000, "Done")
        webSocket = null
    }
    
    interface ProgressListener {
        fun onConnected(data: JSONObject?)
        fun onProgress(progress: Int, step: String, message: String)
        fun onCompleted(itineraryId: String)
        fun onFailed(error: String, canRetry: Boolean, retryAfter: Int?)
        fun onError(error: String)
        fun onDisconnected()
    }
}
```

---

### UI Flow Recommendations

```
┌─────────────────────────────────────┐
│  🛫 Creating Your Trip...           │
├─────────────────────────────────────┤
│                                     │
│  ████████████░░░░░░░░  35%         │
│                                     │
│  ✈️ Searching for best flights...  │
│                                     │
│  [Cancel]                           │
└─────────────────────────────────────┘
          ↓ completed
┌─────────────────────────────────────┐
│  ✅ Your Trip is Ready!             │
├─────────────────────────────────────┤
│                                     │
│  Tokyo 5 Days                       │
│  Jan 15 - Jan 19, 2026              │
│                                     │
│  [View Itinerary]                   │
└─────────────────────────────────────┘
          ↓ failed (can_retry=true)
┌─────────────────────────────────────┐
│  ❌ Something went wrong            │
├─────────────────────────────────────┤
│                                     │
│  Could not complete your request.   │
│  Please try again in 60 seconds.    │
│                                     │
│  [Retry] [Cancel]                   │
└─────────────────────────────────────┘
```

---

### Important Notes

1. **Retry Logic**: ถ้า WebSocket disconnect กลางคัน ให้ reconnect ได้ เพราะจะได้ current status ทันที

2. **Timeout**: ควรตั้ง timeout ~5 นาที ถ้าไม่ได้ `completed`/`failed` ให้แสดง error

3. **Background**: ถ้า app ไป background ให้ตัด WebSocket แล้วใช้ poll API แทน:
   ```
   GET /api/v1/tasks/{task_id}
   ```

4. **Fallback Data**: ถ้า `has_fallback_data: true` แปลว่ามี partial data ให้แสดงพร้อม warning

5. **No Auth Required**: WebSocket endpoint ไม่ต้องส่ง token (task_id เป็น secret)

---

## 📋 Checklist for Mobile Implementation

### Chat Feature
- [ ] Implement chat UI with message bubbles
- [ ] Store and pass `conversation_id` for memory
- [ ] Handle `trigger_planning` response
- [ ] Request location permission for location-based queries
- [ ] Implement typing indicator
- [ ] Handle error states gracefully
- [ ] Add pull-to-refresh for history
- [ ] Implement message retry on failure
- [ ] Add feedback buttons (thumbs up/down)
- [ ] Support Thai and English responses

### WebSocket Progress Tracking
- [ ] Implement WebSocket connection manager
- [ ] Handle all message types (connected, progress, completed, failed, ping)
- [ ] Show progress bar with step description
- [ ] Handle retry on `can_retry: true`
- [ ] Implement reconnection on disconnect
- [ ] Set timeout (5 minutes)
- [ ] Fallback to polling when app goes to background
- [ ] Show partial data warning when `has_fallback_data: true`

---

## 📞 Contact

หากมีคำถามเพิ่มเติม ติดต่อ Backend Team

---

*Document generated for AiGo Mobile Team*
