"""
Tests for conversational AI features in the itinerary domain.

Tests intent classification and response handling.
"""

import pytest
from datetime import datetime, UTC

from app.domains.itinerary.schemas import (
    IntentType,
    DetectedIntent,
    ConversationalResponse,
    TripGenerationResponse,
    ConversationalRequest,
)


class TestIntentTypeEnum:
    """Tests for IntentType enum."""

    def test_intent_type_values(self):
        """Test that IntentType has expected values."""
        assert IntentType.TRIP_GENERATION.value == "trip_generation"
        assert IntentType.GENERAL_INQUIRY.value == "general_inquiry"
        assert IntentType.CHIT_CHAT.value == "chit_chat"
        assert IntentType.DECISION_SUPPORT.value == "decision_support"

    def test_intent_type_count(self):
        """Test that there are exactly 4 intent types."""
        assert len(IntentType) == 4


class TestDetectedIntent:
    """Tests for DetectedIntent schema."""

    def test_detected_intent_minimal(self):
        """Test creating DetectedIntent with minimal data."""
        intent = DetectedIntent(
            intent_type=IntentType.GENERAL_INQUIRY,
            confidence=0.9,
        )
        assert intent.intent_type == IntentType.GENERAL_INQUIRY
        assert intent.confidence == 0.9
        assert intent.requires_search is False
        assert intent.detected_destination is None

    def test_detected_intent_full(self):
        """Test creating DetectedIntent with all fields."""
        intent = DetectedIntent(
            intent_type=IntentType.TRIP_GENERATION,
            confidence=0.95,
            requires_search=True,
            detected_destination="Tokyo",
            detected_dates={"start_date": "2025-04-01", "end_date": "2025-04-07"},
            comparison_items=None,
        )
        assert intent.intent_type == IntentType.TRIP_GENERATION
        assert intent.confidence == 0.95
        assert intent.requires_search is True
        assert intent.detected_destination == "Tokyo"
        assert intent.detected_dates is not None

    def test_detected_intent_decision_support(self):
        """Test creating DetectedIntent for decision support."""
        intent = DetectedIntent(
            intent_type=IntentType.DECISION_SUPPORT,
            confidence=0.85,
            comparison_items=["Kyoto", "Osaka"],
        )
        assert intent.intent_type == IntentType.DECISION_SUPPORT
        assert intent.comparison_items == ["Kyoto", "Osaka"]

    def test_confidence_validation_range(self):
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            DetectedIntent(
                intent_type=IntentType.CHIT_CHAT,
                confidence=1.5,
            )
        with pytest.raises(ValueError):
            DetectedIntent(
                intent_type=IntentType.CHIT_CHAT,
                confidence=-0.1,
            )


class TestConversationalResponse:
    """Tests for ConversationalResponse schema."""

    def test_conversational_response_general_inquiry(self):
        """Test creating a general inquiry response."""
        response = ConversationalResponse(
            intent=IntentType.GENERAL_INQUIRY,
            message="ญี่ปุ่นใช้ปลั๊กไฟแบบ Type A (2 ขาแบน)",
            suggestions=["ดูรายการสิ่งที่ต้องเตรียม", "เริ่มวางแผนทริป"],
            sources=["AiGO Knowledge Base"],
            created_at=datetime.now(UTC),
        )
        assert response.intent == IntentType.GENERAL_INQUIRY
        assert "Type A" in response.message
        assert len(response.suggestions) == 2

    def test_conversational_response_chit_chat(self):
        """Test creating a chit chat response."""
        response = ConversationalResponse(
            intent=IntentType.CHIT_CHAT,
            message="ยินดีด้วยครับ! 🎉",
            suggestions=None,
            created_at=datetime.now(UTC),
        )
        assert response.intent == IntentType.CHIT_CHAT
        assert response.suggestions is None

    def test_conversational_response_decision_support(self):
        """Test creating a decision support response."""
        response = ConversationalResponse(
            intent=IntentType.DECISION_SUPPORT,
            message="เปรียบเทียบ: Kyoto vs Osaka...",
            suggestions=["จัดทริปโอซาก้า", "จัดทริปเกียวโต"],
            sources=["AiGO Knowledge Base"],
            created_at=datetime.now(UTC),
        )
        assert response.intent == IntentType.DECISION_SUPPORT
        assert response.sources is not None


class TestTripGenerationResponse:
    """Tests for TripGenerationResponse schema."""

    def test_trip_generation_response(self):
        """Test creating a trip generation response."""
        from uuid import uuid4
        from app.domains.itinerary.models import ItineraryStatus

        itinerary_id = uuid4()
        response = TripGenerationResponse(
            intent=IntentType.TRIP_GENERATION,
            itinerary_id=itinerary_id,
            task_id="celery-task-123",
            status=ItineraryStatus.PROCESSING,
            message="กำลังวางแผนทริปโตเกียว...",
            websocket_url="/api/v1/ws/itinerary/celery-task-123",
            poll_url="/api/v1/tasks/celery-task-123",
            created_at=datetime.now(UTC),
        )
        assert response.intent == IntentType.TRIP_GENERATION
        assert response.itinerary_id == itinerary_id
        assert response.task_id == "celery-task-123"
        assert response.status == ItineraryStatus.PROCESSING


class TestConversationalRequest:
    """Tests for ConversationalRequest schema."""

    def test_conversational_request_valid(self):
        """Test creating a valid conversational request."""
        request = ConversationalRequest(
            prompt="อยากไปเที่ยวโตเกียว 5 วัน งบ 50000 บาท"
        )
        assert "โตเกียว" in request.prompt

    def test_conversational_request_minimal(self):
        """Test creating request with minimal prompt."""
        request = ConversationalRequest(prompt="สวัสดี")
        assert request.prompt == "สวัสดี"

    def test_conversational_request_english(self):
        """Test creating request with English prompt."""
        request = ConversationalRequest(
            prompt="Plan a 5-day trip to Tokyo with focus on food"
        )
        assert "Tokyo" in request.prompt

    def test_conversational_request_empty_rejected(self):
        """Test that empty prompt is rejected."""
        with pytest.raises(ValueError):
            ConversationalRequest(prompt="")


class TestIntentClassificationPrompts:
    """Tests for intent classification patterns (without LLM)."""

    @pytest.fixture
    def sample_prompts(self):
        """Sample prompts for different intent types."""
        return {
            "trip_generation": [
                "วางแผนเที่ยวโตเกียว 5 วัน",
                "จัดทริปญี่ปุ่นให้หน่อย งบ 50000",
                "Plan a trip to Tokyo",
                "I want to visit Kyoto for 3 days",
            ],
            "general_inquiry": [
                "ญี่ปุ่นใช้ปลั๊กไฟแบบไหน?",
                "แลกเงินเยนที่ไหนเรทดี?",
                "ต้องทำวีซ่าไปญี่ปุ่นไหม?",
                "Do I need a visa for Japan?",
            ],
            "chit_chat": [
                "สวัสดีครับ",
                "ตื่นเต้นจังเลย",
                "ขอบคุณมากครับ",
                "Hello",
            ],
            "decision_support": [
                "เกียวโตกับโอซาก้าที่ไหนดีกว่า?",
                "ไปญี่ปุ่นช่วงไหนดี?",
                "Should I visit Tokyo or Osaka?",
            ],
        }

    def test_sample_prompts_exist(self, sample_prompts):
        """Test that sample prompts are defined for all intent types."""
        assert len(sample_prompts) == 4
        for intent_type, prompts in sample_prompts.items():
            assert len(prompts) > 0, f"No prompts for {intent_type}"


class TestConversationalHandlerSuggestions:
    """Tests for suggestion generation functions."""

    def test_thai_language_detection(self):
        """Test Thai language detection logic."""
        thai_text = "สวัสดีครับ"
        english_text = "Hello"

        # Simple Thai detection
        def is_thai(text):
            return any(
                ord(c) >= 0x0E00 and ord(c) <= 0x0E7F
                for c in text
            )

        assert is_thai(thai_text) is True
        assert is_thai(english_text) is False
