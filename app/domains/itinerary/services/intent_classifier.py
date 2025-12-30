"""
AiGo Backend - Intent Classifier Service
Classifies user prompts into intent categories for the generate endpoint.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.domains.itinerary.schemas import DetectedIntent, IntentType

logger = logging.getLogger(__name__)


# ============ LLM Configuration ============


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Get configured ChatOpenAI instance for intent classification."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Intent Classification Prompt ============


INTENT_CLASSIFICATION_PROMPT = """You are an intelligent conversation classifier for AiGO, a Thai AI travel assistant.

Analyze the user's message and classify their intent into one of these categories:

1. **TRIP_GENERATION** - User wants to create/plan a travel itinerary
   Examples:
   - "วางแผนเที่ยวโตเกียว 5 วัน"
   - "จัดทริปญี่ปุ่นให้หน่อย งบ 50000"
   - "Plan a trip to Tokyo"
   - "I want to visit Kyoto for 3 days"
   - "อยากไปเที่ยวเกาหลี 7 วัน งบ 80000 บาท"

2. **GENERAL_INQUIRY** - User asks factual questions about travel
   Examples:
   - "ญี่ปุ่นใช้ปลั๊กไฟแบบไหน?"
   - "แลกเงินเยนที่ไหนเรทดี?"
   - "ต้องทำวีซ่าไปญี่ปุ่นไหม?"
   - "What's the weather like in Tokyo in April?"
   - "Do I need a visa for Japan?"

3. **CHIT_CHAT** - User is chatting, expressing emotions, greeting, or making small talk
   Examples:
   - "สวัสดีครับ"
   - "ตื่นเต้นจังเลย"
   - "ขอบคุณมากครับ"
   - "Hello"
   - "I'm so excited about my trip!"

4. **DECISION_SUPPORT** - User wants to compare destinations/options before deciding
   Examples:
   - "เกียวโตกับโอซาก้าที่ไหนดีกว่า?"
   - "ไปญี่ปุ่นช่วงไหนดี?"
   - "ระหว่างเกียวโตกับโอซาก้า ที่ไหนเหมาะกับสายกินมากกว่ากัน?"
   - "Should I visit Tokyo or Osaka?"
   - "Which is better for food: Kyoto or Osaka?"

Today's date: {today_date}

User Message:
{user_message}

Respond in JSON format with these fields:
{{
  "intent_type": "trip_generation" | "general_inquiry" | "chit_chat" | "decision_support",
  "confidence": 0.0-1.0,
  "requires_search": true/false (whether external data lookup is needed),
  "detected_destination": "destination name" | null,
  "detected_dates": {{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "duration_days": N}} | null,
  "comparison_items": ["item1", "item2"] | null (for decision_support only)
}}

Guidelines:
- Be smart about detecting intent from context
- Trip generation requires explicit planning keywords like "จัด", "วางแผน", "plan", "trip"
- Questions about facts are general inquiries, not trip generation
- Comparing options = decision support
- Greetings, thanks, emotions = chit chat
- If unsure, lean towards general_inquiry (confidence < 0.7)

Return ONLY valid JSON, no markdown."""


# ============ Intent Classification Function ============


async def classify_intent(user_message: str) -> DetectedIntent:
    """
    Classify user message intent using LLM.

    Args:
        user_message: The user's input message/prompt

    Returns:
        DetectedIntent with classified intent type and extracted entities
    """
    logger.info(f"Classifying intent for message: {user_message[:50]}...")

    llm = get_llm(temperature=0.3)

    prompt = ChatPromptTemplate.from_template(INTENT_CLASSIFICATION_PROMPT)

    today = date.today()
    messages = prompt.format_messages(
        today_date=today.isoformat(),
        user_message=user_message,
    )

    try:
        response = await llm.ainvoke(messages)

        # Parse JSON response
        content = response.content.strip()

        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        intent_data = json.loads(content)

        # Normalize intent_type to match enum values
        intent_type_raw = intent_data.get("intent_type", "general_inquiry")
        intent_type_map = {
            "trip_generation": IntentType.TRIP_GENERATION,
            "general_inquiry": IntentType.GENERAL_INQUIRY,
            "chit_chat": IntentType.CHIT_CHAT,
            "decision_support": IntentType.DECISION_SUPPORT,
        }
        intent_type = intent_type_map.get(
            intent_type_raw.lower(),
            IntentType.GENERAL_INQUIRY,
        )

        detected = DetectedIntent(
            intent_type=intent_type,
            confidence=float(intent_data.get("confidence", 0.5)),
            requires_search=intent_data.get("requires_search", False),
            detected_destination=intent_data.get("detected_destination"),
            detected_dates=intent_data.get("detected_dates"),
            comparison_items=intent_data.get("comparison_items"),
        )

        logger.info(
            f"Classified intent: {detected.intent_type.value} "
            f"(confidence: {detected.confidence:.2f})"
        )

        return detected

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse intent classification response: {e}")
        # Return default general inquiry on parse error
        return DetectedIntent(
            intent_type=IntentType.GENERAL_INQUIRY,
            confidence=0.3,
            requires_search=False,
        )
    except ValidationError as e:
        logger.error(f"Validation error in intent classification: {e}")
        return DetectedIntent(
            intent_type=IntentType.GENERAL_INQUIRY,
            confidence=0.3,
            requires_search=False,
        )
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Return default general inquiry on any error
        return DetectedIntent(
            intent_type=IntentType.GENERAL_INQUIRY,
            confidence=0.3,
            requires_search=False,
        )
