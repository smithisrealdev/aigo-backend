"""
AiGo Backend - Conversational AI Router
Routes user inputs to appropriate handlers: Planning, General Inquiry, or Chit-chat
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============ Intent Types ============


class ConversationIntent(str, Enum):
    """Types of conversation intents."""
    
    PLANNING = "planning"  # Create/modify itinerary
    GENERAL_INQUIRY = "general_inquiry"  # Travel info, questions
    CHIT_CHAT = "chit_chat"  # Casual conversation, support


class IntentClassification(BaseModel):
    """Classified intent from user message."""
    
    intent: ConversationIntent = Field(..., description="Classified intent type")
    confidence: float = Field(..., description="Confidence score 0-1")
    reasoning: str = Field(..., description="Why this intent was chosen")
    keywords: list[str] = Field(default_factory=list, description="Key phrases detected")
    requires_action: bool = Field(default=False, description="Needs external API/action")


# ============ Conversation State ============


class ConversationState(TypedDict):
    """State for conversational AI flow."""
    
    # Input
    user_message: str
    user_id: str | None
    conversation_id: str
    itinerary_id: str | None  # If in context of an itinerary
    
    # Conversation history
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Intent classification
    intent: IntentClassification | None
    
    # Response
    response: str | None
    response_data: dict[str, Any] | None
    
    # Metadata
    current_location: dict | None  # User's GPS location
    current_weather: dict | None
    context: dict[str, Any] | None  # Additional context
    
    # Error handling
    error: str | None


# ============ LLM Configuration ============


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Get configured ChatOpenAI instance."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Prompts ============


INTENT_CLASSIFICATION_PROMPT = """You are an intelligent conversation router for AiGo, an AI travel assistant.

Analyze the user's message and classify it into one of these categories:

1. **PLANNING**: User wants to create, modify, or get recommendations for a trip itinerary
   Examples:
   - "จัดทริปให้หน่อย"
   - "ไปโตเกียว 5 วัน งบ 5 หมื่น"
   - "เปลี่ยนแผนวันที่ 3 ให้หน่อย"
   - "แนะนำที่เที่ยวโตเกียวหน่อย"

2. **GENERAL_INQUIRY**: User asks for travel information, tips, or specific knowledge
   Examples:
   - "พรุ่งนี้ที่โตเกียวมีเทศกาลอะไรไหม?"
   - "เงินเยนเรทตอนนี้เท่าไหร่?"
   - "ปลั๊กที่ญี่ปุ่นเป็นแบบไหน?"
   - "Shibuya Sky ต้องจองล่วงหน้ากี่วัน?"
   - "มีร้านราเมงใกล้ๆ ไหม?" (with location context)

3. **CHIT_CHAT**: Casual conversation, gratitude, emotional support
   Examples:
   - "ขอบคุณมากนะ"
   - "วันนี้เหนื่อยจัง"
   - "แอปนี้เจ๋งดี"
   - "สวัสดี"

Conversation History:
{conversation_history}

Current Message:
{user_message}

Additional Context:
{context}

Respond in JSON format:
{{
  "intent": "planning" | "general_inquiry" | "chit_chat",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "keywords": ["key", "phrases"],
  "requires_action": true/false
}}

Be smart about context:
- If user says "แล้วอากาศเป็นไง?" after talking about Tokyo, it's GENERAL_INQUIRY
- If user says "เปลี่ยนให้หน่อย" after seeing itinerary, it's PLANNING
- Consider conversation flow and user intent"""


GENERAL_INQUIRY_PROMPT = """You are AiGo, a knowledgeable and friendly travel assistant.

Answer the user's travel-related question with accurate, helpful information.

User Question:
{user_message}

Conversation Context:
{conversation_history}

Additional Context:
{context}

Current Location: {current_location}
Current Weather: {current_weather}

Guidelines:
1. Be accurate and specific with facts (dates, numbers, requirements)
2. If you don't know, admit it and suggest where to find info
3. Use emojis sparingly but effectively (🗾 🍜 ⛩️ 🌸)
4. Keep responses conversational and friendly
5. If location-based question, consider user's current position
6. Suggest follow-up actions if relevant

Respond in a natural, helpful tone. Use Thai or English based on user's language."""


CHIT_CHAT_PROMPT = """You are AiGo, a warm and empathetic travel companion AI.

Respond to the user's message with genuine care and personality.

User Message:
{user_message}

Conversation History:
{conversation_history}

Context:
{context}

Personality Traits:
- Friendly and encouraging
- Empathetic to travel fatigue/challenges
- Celebrates travel wins with user
- Provides emotional support
- Uses appropriate emojis (😊 ✨ 🎉 💪)

Guidelines:
1. Acknowledge user's feelings
2. Be supportive and positive
3. Keep it brief but warm
4. Connect to travel context if possible
5. Suggest practical help if user seems tired/stressed

Example Responses:
- "ขอบคุณมากนะ" → "ยินดีมากเลยครับ! 😊 มีอะไรให้ช่วยเพิ่มเติม บอกได้ตลอดเลยนะ"
- "วันนี้เหนื่อยจัง" → "เข้าใจเลยครับ 💪 วันนี้เดินไปกว่า [X] ก้าวแล้ว! แวะพักกันก่อนดีไหมครับ อาจจะหาร้านนวดหรือคาเฟ่น่านั่งก็ได้"

Respond naturally in the user's language (Thai/English)."""


PLANNING_HANDOFF_PROMPT = """Acknowledge that you'll help with planning and gather necessary details.

User Request:
{user_message}

Conversation History:
{conversation_history}

If the request is clear and complete (destination, dates, budget):
- Confirm details and say you're creating the itinerary
- Example: "เข้าใจแล้วครับ! จะจัดแผน {destination} {duration} วัน งบ {budget} ให้เลยนะครับ รอแปปนึงนะ ✨"

If details are missing:
- Ask for missing information naturally
- Example: "โอเค! อยากไป {destination} สักกี่วันครับ? แล้วงบประมาณประมาณเท่าไหร่ดีครับ?"

Respond warmly and efficiently. Use emojis: ✨ 🎯 📝"""


# ============ Node Functions ============


async def intent_router_node(state: ConversationState) -> dict:
    """
    Classify user intent using LLM.
    
    Routes to: planning, general_inquiry, or chit_chat.
    """
    logger.info(f"Routing conversation {state['conversation_id']}")
    
    llm = get_llm(temperature=0.3)  # Lower temp for classification
    
    # Build conversation history string
    history_msgs = state.get("messages", [])
    conversation_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
        for m in history_msgs[-5:]  # Last 5 messages
    ])
    
    # Build context string
    context_parts = []
    if state.get("itinerary_id"):
        context_parts.append(f"User has active itinerary: {state['itinerary_id']}")
    if state.get("current_location"):
        loc = state["current_location"]
        context_parts.append(f"User location: {loc.get('city', 'unknown')}")
    context_str = "\n".join(context_parts) if context_parts else "No additional context"
    
    prompt = ChatPromptTemplate.from_template(INTENT_CLASSIFICATION_PROMPT)
    messages = prompt.format_messages(
        conversation_history=conversation_history or "No previous conversation",
        user_message=state["user_message"],
        context=context_str,
    )
    
    try:
        response = await llm.ainvoke(messages)
        
        # Parse JSON response
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        intent_data = json.loads(content)
        intent = IntentClassification(**intent_data)
        
        logger.info(f"Classified intent: {intent.intent} (confidence: {intent.confidence})")
        
        return {
            "intent": intent,
            "messages": [HumanMessage(content=state["user_message"])],
        }
        
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Default to general inquiry on error
        return {
            "intent": IntentClassification(
                intent=ConversationIntent.GENERAL_INQUIRY,
                confidence=0.5,
                reasoning="Fallback due to classification error",
                keywords=[],
                requires_action=False,
            ),
            "messages": [HumanMessage(content=state["user_message"])],
        }


async def general_inquiry_node(state: ConversationState) -> dict:
    """
    Handle general travel inquiries.
    
    Uses LLM knowledge (and optionally web search) to answer questions.
    """
    logger.info("Handling general inquiry")
    
    llm = get_llm(temperature=0.7)
    
    # Build context
    history_msgs = state.get("messages", [])
    conversation_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
        for m in history_msgs[-5:]
    ])
    
    context_str = ""
    if state.get("itinerary_id"):
        context_str += f"User is currently planning trip ID: {state['itinerary_id']}\n"
    if state.get("context"):
        context_str += f"Additional context: {state['context']}\n"
    
    current_location = state.get("current_location", {})
    location_str = current_location.get("city", "unknown") if current_location else "unknown"
    
    current_weather = state.get("current_weather", {})
    weather_str = f"{current_weather.get('temp')}°C, {current_weather.get('condition')}" if current_weather else "unknown"
    
    prompt = ChatPromptTemplate.from_template(GENERAL_INQUIRY_PROMPT)
    messages = prompt.format_messages(
        user_message=state["user_message"],
        conversation_history=conversation_history or "No previous conversation",
        context=context_str or "No additional context",
        current_location=location_str,
        current_weather=weather_str,
    )
    
    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()
        
        logger.info(f"Generated inquiry response: {answer[:100]}...")
        
        return {
            "response": answer,
            "messages": [AIMessage(content=answer)],
        }
        
    except Exception as e:
        logger.error(f"General inquiry failed: {e}")
        return {
            "response": "ขอโทษครับ ตอนนี้มีปัญหานิดหน่อย ช่วยถามใหม่อีกทีได้ไหมครับ 🙏",
            "error": str(e),
        }


async def chit_chat_node(state: ConversationState) -> dict:
    """
    Handle casual conversation and emotional support.
    """
    logger.info("Handling chit-chat")
    
    llm = get_llm(temperature=0.9)  # Higher temp for personality
    
    history_msgs = state.get("messages", [])
    conversation_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
        for m in history_msgs[-5:]
    ])
    
    context_str = ""
    if state.get("context"):
        context_str = f"Context: {state['context']}\n"
    
    prompt = ChatPromptTemplate.from_template(CHIT_CHAT_PROMPT)
    messages = prompt.format_messages(
        user_message=state["user_message"],
        conversation_history=conversation_history or "No previous conversation",
        context=context_str or "No additional context",
    )
    
    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()
        
        logger.info(f"Generated chit-chat response: {answer[:100]}...")
        
        return {
            "response": answer,
            "messages": [AIMessage(content=answer)],
        }
        
    except Exception as e:
        logger.error(f"Chit-chat failed: {e}")
        return {
            "response": "😊 ยินดีเสมอครับ! มีอะไรให้ช่วยเพิ่มเติมไหมครับ?",
            "error": str(e),
        }


async def planning_handoff_node(state: ConversationState) -> dict:
    """
    Handle planning requests.
    
    Either acknowledges and hands off to planner workflow,
    or asks for missing details.
    """
    logger.info("Handling planning request")
    
    llm = get_llm(temperature=0.7)
    
    history_msgs = state.get("messages", [])
    conversation_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
        for m in history_msgs[-5:]
    ])
    
    prompt = ChatPromptTemplate.from_template(PLANNING_HANDOFF_PROMPT)
    messages = prompt.format_messages(
        user_message=state["user_message"],
        conversation_history=conversation_history or "No previous conversation",
    )
    
    try:
        response = await llm.ainvoke(messages)
        answer = response.content.strip()
        
        logger.info(f"Planning handoff response: {answer[:100]}...")
        
        return {
            "response": answer,
            "messages": [AIMessage(content=answer)],
            "response_data": {
                "trigger_planning": True,  # Signal to trigger planner workflow
                "user_prompt": state["user_message"],
            },
        }
        
    except Exception as e:
        logger.error(f"Planning handoff failed: {e}")
        return {
            "response": "เข้าใจแล้วครับ! ช่วยบอกรายละเอียดเพิ่มเติมนิดนึงได้ไหมครับ เช่น จะไปที่ไหน กี่วัน งบประมาณเท่าไหร่ครับ? 📝",
            "error": str(e),
        }


# ============ Routing Logic ============


def route_by_intent(state: ConversationState) -> Literal["planning", "general_inquiry", "chit_chat", "end"]:
    """Route to appropriate handler based on classified intent."""
    intent = state.get("intent")
    
    if not intent:
        return "end"
    
    if intent.intent == ConversationIntent.PLANNING:
        return "planning"
    elif intent.intent == ConversationIntent.GENERAL_INQUIRY:
        return "general_inquiry"
    elif intent.intent == ConversationIntent.CHIT_CHAT:
        return "chit_chat"
    else:
        return "end"


# ============ Build Graph ============


def build_conversation_graph() -> StateGraph:
    """
    Build the conversation routing graph.
    
    Flow:
    1. Intent Router - Classify user message
    2. Route to appropriate handler:
       - Planning → Planning handoff
       - General Inquiry → Answer with knowledge/search
       - Chit-chat → Empathetic response
    """
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("intent_router", intent_router_node)
    workflow.add_node("planning", planning_handoff_node)
    workflow.add_node("general_inquiry", general_inquiry_node)
    workflow.add_node("chit_chat", chit_chat_node)
    
    # Set entry point
    workflow.set_entry_point("intent_router")
    
    # Add conditional routing from intent_router
    workflow.add_conditional_edges(
        "intent_router",
        route_by_intent,
        {
            "planning": "planning",
            "general_inquiry": "general_inquiry",
            "chit_chat": "chit_chat",
            "end": END,
        },
    )
    
    # All handlers end
    workflow.add_edge("planning", END)
    workflow.add_edge("general_inquiry", END)
    workflow.add_edge("chit_chat", END)
    
    return workflow


# Create memory checkpointer for conversation history
memory_checkpointer = MemorySaver()

# Compile the graph with memory
conversation_graph = build_conversation_graph().compile(checkpointer=memory_checkpointer)


# ============ Public Interface ============


async def route_conversation(
    user_message: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    itinerary_id: str | None = None,
    current_location: dict | None = None,
    current_weather: dict | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Route user message through conversational AI.
    
    Args:
        user_message: User's input message
        user_id: Optional user ID
        conversation_id: Conversation thread ID (for memory)
        itinerary_id: If in context of an itinerary
        current_location: User's GPS location
        current_weather: Current weather data
        context: Additional context
        
    Returns:
        Dict with response, intent, and metadata
    """
    # Generate conversation ID if not provided
    if not conversation_id:
        import uuid
        conversation_id = str(uuid.uuid4())
    
    initial_state: ConversationState = {
        "user_message": user_message,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "itinerary_id": itinerary_id,
        "messages": [],
        "intent": None,
        "response": None,
        "response_data": None,
        "current_location": current_location,
        "current_weather": current_weather,
        "context": context,
        "error": None,
    }
    
    try:
        # Run with checkpointer for conversation memory
        config = {"configurable": {"thread_id": conversation_id}}
        
        final_state = await conversation_graph.ainvoke(initial_state, config)
        
        return {
            "success": True,
            "response": final_state.get("response"),
            "intent": final_state.get("intent").intent.value if final_state.get("intent") else None,
            "confidence": final_state.get("intent").confidence if final_state.get("intent") else None,
            "response_data": final_state.get("response_data"),
            "conversation_id": conversation_id,
            "error": final_state.get("error"),
        }
        
    except Exception as e:
        logger.error(f"Conversation routing failed: {e}")
        return {
            "success": False,
            "response": "ขอโทษครับ มีปัญหาเกิดขึ้น ช่วยลองใหม่อีกทีได้ไหมครับ 🙏",
            "error": str(e),
            "conversation_id": conversation_id,
        }
