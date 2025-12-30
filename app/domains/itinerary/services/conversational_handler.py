"""
AiGo Backend - Conversational Handler Service
Handles non-trip-generation intents: general inquiry, chit-chat, decision support.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.domains.itinerary.schemas import (
    ConversationalResponse,
    DetectedIntent,
    IntentType,
)

logger = logging.getLogger(__name__)


# ============ LLM Configuration ============


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Get configured ChatOpenAI instance for conversational responses."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Prompts ============


GENERAL_INQUIRY_PROMPT = """You are AiGO, a friendly Thai travel buddy AI assistant.
You are knowledgeable, helpful, and enthusiastic about travel.

User's Question:
{user_message}

Detected Context:
- Destination: {destination}
- Requires real-time search: {requires_search}

Guidelines:
1. Provide accurate, helpful information about:
   - Visa requirements, local customs, laws
   - Currency exchange, power plugs, SIM cards
   - Transportation options, safety tips
   - Weather patterns, best seasons to visit
2. Use the same language as the user (Thai or English)
3. Be conversational and friendly
4. Use relevant emojis sparingly: 🔌 💴 🗾 ✈️ 🌸
5. If you're not 100% certain, say so and recommend official sources
6. End with 1-2 helpful follow-up suggestions

Format your response naturally, not as bullet points unless appropriate."""


CHIT_CHAT_PROMPT = """You are AiGO, a warm and empathetic Thai travel buddy AI assistant.
You're friendly, encouraging, and genuinely excited to help people with their travel adventures.

User's Message:
{user_message}

Guidelines:
1. Acknowledge the user's feelings with warmth
2. Be supportive and positive
3. Keep responses brief but genuine
4. Connect to travel context when appropriate
5. Use emojis that match the mood: 😊 🎉 ✨ 💪 🌟
6. Respond in the same language as the user (Thai or English)
7. Offer to help with travel planning if appropriate

Example Responses:
- "สวัสดีครับ" → "สวัสดีครับ! 😊 ยินดีที่ได้พบกันนะครับ มีแผนจะไปเที่ยวที่ไหนกันบ้างครับ?"
- "ตื่นเต้นจังเลย" → "ยินดีด้วยครับ! 🎉 ความตื่นเต้นก่อนเดินทางนี่สุดยอดเลย บอกผมได้เลยนะครับว่าจะไปที่ไหน ผมจะช่วยวางแผนให้!"
- "Thank you!" → "You're welcome! 😊 Happy to help. Let me know if you need anything else for your trip!"

Respond naturally and warmly."""


DECISION_SUPPORT_PROMPT = """You are AiGO, a knowledgeable Thai travel buddy AI assistant.
Help the user make an informed decision by comparing options fairly.

User's Question:
{user_message}

Items to Compare: {comparison_items}
Detected Destination Context: {destination}

Guidelines:
1. Provide a balanced comparison with pros and cons
2. Use clear formatting with headers and bullet points
3. Consider different traveler types (budget, luxury, foodie, culture, etc.)
4. Give a clear recommendation with reasoning
5. Use relevant emojis: 🏯 🍜 🛍️ 🎌 ⛩️
6. Respond in the same language as the user (Thai or English)
7. End with follow-up suggestions

Format Example:
🏯 **Option A (e.g., Kyoto)**
✅ Pros: ...
❌ Cons: ...

🌃 **Option B (e.g., Osaka)**
✅ Pros: ...
❌ Cons: ...

**สรุป/Summary:** [Clear recommendation with reasoning]

Provide helpful, balanced analysis."""


# ============ Handler Functions ============


async def handle_general_inquiry(
    user_message: str,
    intent: DetectedIntent,
) -> ConversationalResponse:
    """
    Handle general travel inquiry.

    Args:
        user_message: User's question
        intent: Detected intent with context

    Returns:
        ConversationalResponse with helpful travel information
    """
    logger.info("Handling general inquiry")

    llm = get_llm(temperature=0.7)

    prompt = ChatPromptTemplate.from_template(GENERAL_INQUIRY_PROMPT)
    messages = prompt.format_messages(
        user_message=user_message,
        destination=intent.detected_destination or "not specified",
        requires_search=str(intent.requires_search),
    )

    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()

        # Generate suggestions based on context
        suggestions = _generate_inquiry_suggestions(user_message, intent)

        logger.info(f"Generated inquiry response: {answer[:100]}...")

        return ConversationalResponse(
            intent=IntentType.GENERAL_INQUIRY,
            message=answer,
            suggestions=suggestions,
            sources=["AiGO Knowledge Base"],
            created_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.error(f"General inquiry handler failed: {e}")
        return ConversationalResponse(
            intent=IntentType.GENERAL_INQUIRY,
            message="ขอโทษครับ ตอนนี้มีปัญหานิดหน่อย ลองถามใหม่อีกทีได้ไหมครับ 🙏",
            suggestions=["ลองถามคำถามอื่น", "เริ่มวางแผนทริป"],
            created_at=datetime.now(UTC),
        )


async def handle_chit_chat(
    user_message: str,
    intent: DetectedIntent,
) -> ConversationalResponse:
    """
    Handle casual conversation and emotional support.

    Args:
        user_message: User's message
        intent: Detected intent

    Returns:
        ConversationalResponse with friendly, empathetic reply
    """
    logger.info("Handling chit-chat")

    llm = get_llm(temperature=0.9)  # Higher temp for personality

    prompt = ChatPromptTemplate.from_template(CHIT_CHAT_PROMPT)
    messages = prompt.format_messages(user_message=user_message)

    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()

        # Generate contextual suggestions
        suggestions = _generate_chit_chat_suggestions(user_message)

        logger.info(f"Generated chit-chat response: {answer[:100]}...")

        return ConversationalResponse(
            intent=IntentType.CHIT_CHAT,
            message=answer,
            suggestions=suggestions,
            created_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.error(f"Chit-chat handler failed: {e}")
        return ConversationalResponse(
            intent=IntentType.CHIT_CHAT,
            message="😊 ยินดีเสมอครับ! มีอะไรให้ช่วยเพิ่มเติมไหมครับ?",
            suggestions=["เริ่มวางแผนทริป", "ถามคำถามเกี่ยวกับการเดินทาง"],
            created_at=datetime.now(UTC),
        )


async def handle_decision_support(
    user_message: str,
    intent: DetectedIntent,
) -> ConversationalResponse:
    """
    Handle decision support for comparing travel options.

    Args:
        user_message: User's comparison question
        intent: Detected intent with comparison items

    Returns:
        ConversationalResponse with balanced comparison and recommendation
    """
    logger.info("Handling decision support")

    llm = get_llm(temperature=0.7)

    prompt = ChatPromptTemplate.from_template(DECISION_SUPPORT_PROMPT)
    messages = prompt.format_messages(
        user_message=user_message,
        comparison_items=", ".join(intent.comparison_items or ["Unknown"]),
        destination=intent.detected_destination or "not specified",
    )

    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()

        # Generate suggestions based on comparison items
        suggestions = _generate_decision_suggestions(intent)

        logger.info(f"Generated decision support response: {answer[:100]}...")

        return ConversationalResponse(
            intent=IntentType.DECISION_SUPPORT,
            message=answer,
            suggestions=suggestions,
            sources=["AiGO Knowledge Base"],
            created_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.error(f"Decision support handler failed: {e}")
        return ConversationalResponse(
            intent=IntentType.DECISION_SUPPORT,
            message="ขอโทษครับ ตอนนี้มีปัญหานิดหน่อย ลองถามใหม่อีกทีได้ไหมครับ 🙏",
            suggestions=["ลองถามคำถามอื่น", "เริ่มวางแผนทริป"],
            created_at=datetime.now(UTC),
        )


# ============ Suggestion Generators ============


def _generate_inquiry_suggestions(
    user_message: str,
    intent: DetectedIntent,
) -> list[str]:
    """Generate follow-up suggestions for general inquiries."""
    suggestions = []

    # If destination is mentioned, suggest trip planning
    if intent.detected_destination:
        dest = intent.detected_destination
        suggestions.append(f"วางแผนทริป{dest}ให้หน่อย")
        suggestions.append(f"ดูสิ่งที่ต้องเตรียมไป{dest}")
    else:
        suggestions.append("เริ่มวางแผนทริป")
        suggestions.append("แนะนำจุดหมายยอดนิยม")

    return suggestions[:2]


def _generate_chit_chat_suggestions(user_message: str) -> list[str]:
    """Generate follow-up suggestions for chit-chat."""
    # Detect language and context
    is_thai = any(
        ord(c) >= 0x0E00 and ord(c) <= 0x0E7F
        for c in user_message
    )

    if is_thai:
        return [
            "เล่าให้ฟังหน่อยว่าชอบเที่ยวแบบไหน",
            "เริ่มวางแผนทริปกันเลย",
        ]
    else:
        return [
            "Tell me about your travel style",
            "Let's start planning your trip",
        ]


def _generate_decision_suggestions(intent: DetectedIntent) -> list[str]:
    """Generate follow-up suggestions for decision support."""
    suggestions = []

    if intent.comparison_items:
        # Suggest planning for one of the options
        for item in intent.comparison_items[:2]:
            suggestions.append(f"จัดทริป{item}ให้หน่อย")

    if not suggestions:
        suggestions = [
            "เริ่มวางแผนทริป",
            "อยากไปทั้งสองที่ เป็นไปได้ไหม?",
        ]

    return suggestions[:2]


# ============ Main Handler Dispatcher ============


async def handle_conversational_intent(
    user_message: str,
    intent: DetectedIntent,
) -> ConversationalResponse:
    """
    Route to appropriate handler based on detected intent.

    Args:
        user_message: User's message
        intent: Detected intent

    Returns:
        ConversationalResponse from the appropriate handler
    """
    handlers = {
        IntentType.GENERAL_INQUIRY: handle_general_inquiry,
        IntentType.CHIT_CHAT: handle_chit_chat,
        IntentType.DECISION_SUPPORT: handle_decision_support,
    }

    handler = handlers.get(intent.intent_type)

    if handler:
        return await handler(user_message, intent)
    else:
        # Fallback to general inquiry
        logger.warning(f"No handler for intent type: {intent.intent_type}")
        return await handle_general_inquiry(user_message, intent)
