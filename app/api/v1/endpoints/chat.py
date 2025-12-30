"""
AiGo Backend - Chat API Endpoints
Conversational AI interface for travel assistance
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user_id
from app.domains.chat.services.conversation_router import route_conversation

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Schemas ============


class ChatMessage(BaseModel):
    """Chat message request."""
    
    message: str = Field(..., description="User message", min_length=1, max_length=2000)
    conversation_id: str | None = Field(None, description="Conversation thread ID for memory")
    itinerary_id: str | None = Field(None, description="Active itinerary context")
    current_location: dict | None = Field(None, description="User GPS location {lat, lng, city}")
    current_weather: dict | None = Field(None, description="Current weather data")
    context: dict | None = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """Chat response."""
    
    success: bool
    response: str | None = Field(None, description="AI response text")
    intent: str | None = Field(None, description="Classified intent: planning, general_inquiry, chit_chat")
    confidence: float | None = Field(None, description="Intent confidence score")
    conversation_id: str = Field(..., description="Conversation thread ID")
    response_data: dict | None = Field(None, description="Additional response data")
    error: str | None = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "response": "เข้าใจแล้วครับ! จะจัดแผนโตเกียว 5 วัน งบ 50,000 บาทให้เลยนะครับ รอแปปนึงนะ ✨",
                "intent": "planning",
                "confidence": 0.95,
                "conversation_id": "conv-123",
                "response_data": {
                    "trigger_planning": True,
                    "user_prompt": "อยากไปโตเกียว 5 วัน งบ 5 หมื่น"
                },
                "error": None
            }
        }


class ConversationHistory(BaseModel):
    """Conversation history request."""
    
    conversation_id: str = Field(..., description="Conversation thread ID")
    limit: int = Field(10, description="Number of messages to return", ge=1, le=100)


class ConversationMessage(BaseModel):
    """Single conversation message."""
    
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="ISO timestamp")
    intent: str | None = Field(None, description="Intent if classified")


class ConversationHistoryResponse(BaseModel):
    """Conversation history response."""
    
    conversation_id: str
    messages: list[ConversationMessage]
    total_messages: int


# ============ Endpoints ============


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send message to AI assistant",
    description="""
    Send a message to the conversational AI travel assistant.
    
    The AI will automatically classify your intent and respond appropriately:
    
    **Planning Intent:**
    - "จัดทริปให้หน่อย"
    - "ไปโตเกียว 5 วัน งบ 5 หมื่น"
    - "เปลี่ยนแผนวันที่ 3"
    
    Response: Acknowledges and triggers itinerary generation workflow
    
    **General Inquiry:**
    - "พรุ่งนี้ที่โตเกียวมีเทศกาลอะไรไหม?"
    - "เงินเยนเรทตอนนี้เท่าไหร่?"
    - "Shibuya Sky ต้องจองล่วงหน้ากี่วัน?"
    - "มีร้านราเมงใกล้ๆ ไหม?" (with GPS location)
    
    Response: Direct answer using AI knowledge or web search
    
    **Chit-chat:**
    - "ขอบคุณมากนะ"
    - "วันนี้เหนื่อยจัง"
    - "แอปนี้เจ๋งดี"
    
    Response: Friendly, empathetic response
    
    **Conversation Memory:**
    - Provide `conversation_id` to maintain context across messages
    - AI remembers previous messages and can answer follow-up questions
    - Example: "แล้วอากาศเป็นไง?" after asking about Tokyo
    
    **Context:**
    - `itinerary_id`: If user has an active trip plan
    - `current_location`: User's GPS for location-based queries
    - `current_weather`: Current weather for smart suggestions
    
    Returns the AI response and classified intent.
    """,
)
async def send_chat_message(
    request: ChatMessage,
    user_id: UUID = Depends(get_current_user_id),
) -> ChatResponse:
    """
    Send message to conversational AI.
    
    Handles:
    - Intent classification
    - Conversation memory
    - Context-aware responses
    """
    try:
        # Route through conversational AI
        result = await route_conversation(
            user_message=request.message,
            user_id=str(user_id),
            conversation_id=request.conversation_id,
            itinerary_id=request.itinerary_id,
            current_location=request.current_location,
            current_weather=request.current_weather,
            context=request.context,
        )
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


@router.get(
    "/chat/history/{conversation_id}",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
    description="""
    Retrieve conversation history for a specific thread.
    
    Use this to:
    - Display chat history in UI
    - Resume conversations
    - Debug conversation flow
    
    Messages are returned in chronological order (oldest first).
    """,
)
async def get_conversation_history(
    conversation_id: str,
    limit: int = 10,
    user_id: UUID = Depends(get_current_user_id),
) -> ConversationHistoryResponse:
    """
    Get conversation history.
    
    NOTE: This is a placeholder. In production, you would:
    1. Query conversation history from Redis/Database
    2. Filter by user_id for security
    3. Return formatted messages
    """
    # TODO: Implement actual history retrieval from checkpointer
    logger.info(f"Fetching history for conversation {conversation_id}")
    
    # Placeholder response
    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=[],
        total_messages=0,
    )


@router.delete(
    "/chat/history/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation history",
    description="""
    Delete all messages in a conversation thread.
    
    Use this to:
    - Clear conversation memory
    - Start fresh conversation
    - Delete sensitive data
    """,
)
async def delete_conversation_history(
    conversation_id: str,
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """
    Delete conversation history.
    
    NOTE: This is a placeholder. In production, you would:
    1. Delete conversation from Redis/Database checkpointer
    2. Verify user owns this conversation
    3. Clear associated memory
    """
    # TODO: Implement actual history deletion
    logger.info(f"Deleting history for conversation {conversation_id}")
    
    return None


@router.post(
    "/chat/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit feedback on AI response",
    description="""
    Submit feedback on an AI response (thumbs up/down).
    
    Helps improve AI quality over time.
    """,
)
async def submit_chat_feedback(
    conversation_id: str,
    message_index: int,
    feedback: str,  # "positive" or "negative"
    comment: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """
    Submit feedback on AI response.
    
    NOTE: This is a placeholder for future analytics.
    """
    logger.info(f"Feedback received: {feedback} for conversation {conversation_id}")
    
    # TODO: Store feedback for model improvement
    return None
