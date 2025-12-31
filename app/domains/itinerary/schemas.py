"""Pydantic schemas for the Itinerary domain."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.itinerary.models import ActivityCategory, ItineraryStatus

# ============ Image Schemas ============


class LocationImage(BaseModel):
    """Image for a location/activity."""

    url: str = Field(..., description="Full resolution image URL")
    thumbnail_url: str = Field(..., description="Thumbnail URL for previews")
    width: int | None = Field(None, description="Image width in pixels")
    height: int | None = Field(None, description="Image height in pixels")
    source_url: str | None = Field(None, description="Page where image was found")
    source_domain: str | None = Field(None, description="Domain of the source")
    title: str | None = Field(None, description="Image title/alt text")

    # Attribution
    attribution: str | None = Field(None, description="Image attribution if required")
    license_type: str | None = Field(None, description="License type if known")


class LocationImages(BaseModel):
    """Collection of images for a location."""

    location_name: str = Field(..., description="Name of the location")
    query_used: str = Field(..., description="Search query used")
    images: list[LocationImage] = Field(default_factory=list)

    # Metadata
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_cached: bool = Field(default=False)
    cache_expires_at: datetime | None = None


# ============ Activity Schemas ============


class ActivityBase(BaseModel):
    """Base schema for Activity."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: ActivityCategory = ActivityCategory.SIGHTSEEING
    day_number: int = Field(default=1, ge=1)
    order: int = Field(default=0, ge=0)

    # Location
    location_name: str | None = Field(None, max_length=500)
    location_address: str | None = Field(None, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    google_place_id: str | None = Field(None, max_length=255)

    # Time
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = Field(None, ge=0)

    # Cost
    estimated_cost: Decimal | None = Field(None, ge=0)
    actual_cost: Decimal | None = Field(None, ge=0)

    # Booking
    booking_reference: str | None = Field(None, max_length=255)
    booking_url: str | None = Field(None, max_length=500)
    notes: str | None = None


class ActivityCreate(ActivityBase):
    """Schema for creating an Activity."""

    pass


class ActivityUpdate(BaseModel):
    """Schema for updating an Activity."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category: ActivityCategory | None = None
    day_number: int | None = Field(None, ge=1)
    order: int | None = Field(None, ge=0)
    location_name: str | None = Field(None, max_length=500)
    location_address: str | None = Field(None, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    google_place_id: str | None = Field(None, max_length=255)
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = Field(None, ge=0)
    estimated_cost: Decimal | None = Field(None, ge=0)
    actual_cost: Decimal | None = Field(None, ge=0)
    booking_reference: str | None = Field(None, max_length=255)
    booking_url: str | None = Field(None, max_length=500)
    notes: str | None = None


class ActivityResponse(ActivityBase):
    """Schema for Activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    itinerary_id: UUID
    daily_plan_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


# ============ DailyPlan Schemas ============


class DailyPlanBase(BaseModel):
    """Base schema for DailyPlan."""

    day_number: int = Field(..., ge=1)
    plan_date: date = Field(..., validation_alias="date")
    title: str | None = Field(None, max_length=255)
    notes: str | None = None
    daily_budget: Decimal | None = Field(None, ge=0)


class DailyPlanCreate(BaseModel):
    """Schema for creating a DailyPlan."""

    day_number: int = Field(..., ge=1)
    plan_date: date = Field(..., serialization_alias="date")
    title: str | None = Field(None, max_length=255)
    notes: str | None = None
    daily_budget: Decimal | None = Field(None, ge=0)
    activities: list[ActivityCreate] = Field(default_factory=list)


class DailyPlanUpdate(BaseModel):
    """Schema for updating a DailyPlan."""

    title: str | None = Field(None, max_length=255)
    notes: str | None = None
    daily_budget: Decimal | None = Field(None, ge=0)


class DailyPlanResponse(BaseModel):
    """Schema for DailyPlan response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    itinerary_id: UUID
    day_number: int
    plan_date: date = Field(..., validation_alias="date")
    title: str | None = None
    notes: str | None = None
    daily_budget: Decimal | None = None
    activities: list[ActivityResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ============ Itinerary Schemas ============


class ItineraryBase(BaseModel):
    """Base schema for Itinerary."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    destination: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    total_budget: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="THB", min_length=3, max_length=3)
    status: ItineraryStatus = ItineraryStatus.DRAFT
    cover_image_url: str | None = Field(None, max_length=500)
    is_public: bool = False
    notes: str | None = None

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: date, info) -> date:
        """Validate that end_date is not before start_date."""
        start_date = info.data.get("start_date")
        if start_date and v < start_date:
            raise ValueError("end_date must be on or after start_date")
        return v


class ItineraryCreate(ItineraryBase):
    """Schema for creating an Itinerary."""

    activities: list[ActivityCreate] = Field(default_factory=list)
    daily_plans: list[DailyPlanCreate] = Field(default_factory=list)


class ItineraryUpdate(BaseModel):
    """Schema for updating an Itinerary."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    destination: str | None = Field(None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    total_budget: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    status: ItineraryStatus | None = None
    cover_image_url: str | None = Field(None, max_length=500)
    is_public: bool | None = None
    notes: str | None = None


class ItineraryResponse(ItineraryBase):
    """Schema for Itinerary response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    activities: list[ActivityResponse] = Field(default_factory=list)
    daily_plans: list[DailyPlanResponse] = Field(default_factory=list)

    # AI Generation fields
    original_prompt: str | None = None
    generation_task_id: str | None = None
    generation_error: str | None = None
    completed_at: datetime | None = None

    # Versioning fields
    version: int = 1
    last_replan_at: datetime | None = None
    replan_task_id: str | None = None

    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days + 1


class ItineraryListResponse(BaseModel):
    """Schema for paginated list of Itineraries."""

    items: list[ItineraryResponse]
    total: int
    page: int
    size: int
    pages: int


class ItinerarySummary(BaseModel):
    """Lightweight summary schema for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    destination: str
    start_date: date
    end_date: date
    status: ItineraryStatus
    cover_image_url: str | None = None
    total_budget: Decimal
    currency: str


# ============ AI Generation Schemas ============


class GenerateItineraryRequest(BaseModel):
    """Request schema for AI-powered itinerary generation."""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language description of the desired trip",
        examples=[
            "Plan a 7-day trip to Tokyo for 2 people, focusing on culture and food, budget around $3000",
            "I want to explore Bangkok for 5 days, interested in temples, street food, and nightlife",
        ],
    )
    budget: Decimal = Field(
        ...,
        ge=0,
        description="Total budget for the trip",
        examples=[3000, 50000],
    )
    currency: str = Field(
        default="THB",
        min_length=3,
        max_length=3,
        description="Currency code (ISO 4217)",
        examples=["THB", "USD", "EUR"],
    )
    preferences: dict | None = Field(
        default=None,
        description="Optional preferences for the trip",
        examples=[{
            "pace": "relaxed",
            "interests": ["food", "culture", "shopping"],
            "accommodation_type": "hotel",
            "travel_style": "budget",
        }],
    )


class GenerateItineraryResponse(BaseModel):
    """Response schema for itinerary generation request."""

    itinerary_id: UUID = Field(..., description="ID of the created itinerary")
    task_id: str = Field(..., description="Celery task ID for progress tracking")
    status: ItineraryStatus = Field(..., description="Initial status (PROCESSING)")
    message: str = Field(..., description="Human-readable status message")
    websocket_url: str = Field(..., description="WebSocket URL for real-time progress")
    poll_url: str = Field(..., description="REST URL for polling progress")
    created_at: datetime


class ItineraryWithTaskResponse(ItineraryResponse):
    """Extended itinerary response with task information."""

    original_prompt: str | None = None
    generation_task_id: str | None = None


class ItineraryFullDataResponse(BaseModel):
    """
    Response schema for GET /itinerary/{id} with full AI-generated data.
    
    Returns the complete itinerary with all AI-generated content for mobile rendering.
    """

    model_config = ConfigDict(from_attributes=True)

    # Basic metadata
    id: UUID
    user_id: UUID
    status: ItineraryStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    # Generation info
    original_prompt: str | None = None
    generation_task_id: str | None = None
    generation_error: str | None = None

    # Basic fields (from Itinerary model)
    title: str
    description: str | None = None
    destination: str
    start_date: date
    end_date: date
    total_budget: Decimal
    currency: str
    cover_image_url: str | None = None
    is_public: bool = False
    notes: str | None = None

    # Full AI-generated data (from JSONB field)
    # This contains the complete AIFullItinerary structure
    data: dict | None = Field(
        None,
        description="Complete AI-generated itinerary (AIFullItinerary schema)",
    )

    @property
    def is_ready(self) -> bool:
        """Check if the itinerary is fully generated and ready."""
        return self.status == ItineraryStatus.COMPLETED and self.data is not None

    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days + 1


class ItineraryStatusResponse(BaseModel):
    """Lightweight status check response."""

    id: UUID
    status: ItineraryStatus
    generation_task_id: str | None = None
    generation_error: str | None = None
    completed_at: datetime | None = None
    is_ready: bool = False


# ============ Conversational AI Schemas ============


class IntentType(str, Enum):
    """Types of conversation intents for the generate endpoint."""

    TRIP_GENERATION = "trip_generation"
    GENERAL_INQUIRY = "general_inquiry"
    CHIT_CHAT = "chit_chat"
    DECISION_SUPPORT = "decision_support"


class DetectedIntent(BaseModel):
    """Detected intent from user prompt."""

    intent_type: IntentType = Field(..., description="Classified intent type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    requires_search: bool = Field(
        default=False,
        description="Whether to search for real-time data",
    )
    detected_destination: str | None = Field(
        None,
        description="Destination if mentioned in prompt",
    )
    detected_dates: dict | None = Field(
        None,
        description="Dates if mentioned in prompt",
    )
    comparison_items: list[str] | None = Field(
        None,
        description="Items to compare for decision support",
    )


class ConversationalRequest(BaseModel):
    """Request schema for conversational AI endpoint (simplified)."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's message or travel request",
        examples=[
            "ญี่ปุ่นใช้ปลั๊กไฟแบบไหน?",
            "ตื่นเต้นจังเลย จะได้ไปญี่ปุ่นครั้งแรกแล้ว",
            "ระหว่างเกียวโตกับโอซาก้า ที่ไหนเหมาะกับสายกินมากกว่ากัน?",
            "อยากไปเที่ยวโตเกียว 5 วัน งบ 50000 บาท",
        ],
    )


class ConversationalResponse(BaseModel):
    """Response for non-trip-generation intents."""

    intent: IntentType = Field(..., description="Detected intent type")
    message: str = Field(..., description="AI response message")
    suggestions: list[str] | None = Field(
        None,
        description="Follow-up suggestions for the user",
    )
    sources: list[str] | None = Field(
        None,
        description="Data sources used for the response",
    )
    created_at: datetime = Field(..., description="Response timestamp")


class TripGenerationResponse(BaseModel):
    """Response when trip generation is triggered."""

    intent: IntentType = Field(
        default=IntentType.TRIP_GENERATION,
        description="Intent type (always trip_generation)",
    )
    itinerary_id: UUID = Field(..., description="ID of the created itinerary")
    task_id: str = Field(..., description="Celery task ID for progress tracking")
    status: ItineraryStatus = Field(..., description="Initial status (PROCESSING)")
    message: str = Field(..., description="Human-readable status message")
    websocket_url: str = Field(..., description="WebSocket URL for real-time progress")
    poll_url: str = Field(..., description="REST URL for polling progress")
    created_at: datetime = Field(..., description="Response timestamp")


# ============ Smart Re-plan Schemas ============


class ReplanTriggerType(str, Enum):
    """Types of triggers that can initiate a replan."""

    WEATHER = "weather"
    TRAFFIC = "traffic"
    CROWD = "crowd"
    USER_REQUEST = "user_request"
    SCHEDULE_CHANGE = "schedule_change"
    VENUE_CLOSURE = "venue_closure"


class ReplanReason(str, Enum):
    """Reason categories for replanning."""

    USER_INITIATED = "user_initiated"
    SYSTEM_PROACTIVE = "system_proactive"


class GPSLocation(BaseModel):
    """GPS location for context-aware replanning."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float | None = Field(None, ge=0)
    timestamp: datetime | None = None


class ReplanRequest(BaseModel):
    """Request schema for replanning an itinerary."""

    reason: ReplanReason = Field(
        ...,
        description="Whether replan is user-initiated or system-proactive",
    )
    trigger_type: ReplanTriggerType = Field(
        ...,
        description="The type of trigger causing the replan",
    )
    trigger_details: str | None = Field(
        None,
        max_length=1000,
        description="Additional details about the trigger (e.g., 'Heavy rain expected', 'User wants to skip temple')",
    )
    current_gps_location: GPSLocation | None = Field(
        None,
        description="User's current GPS location for context-aware suggestions",
    )
    affected_day: int | None = Field(
        None,
        ge=1,
        description="Specific day to replan (if not provided, system will determine)",
    )
    affected_activity_ids: list[str] | None = Field(
        None,
        description="Specific activity IDs to consider for replanning",
    )
    user_preferences: dict | None = Field(
        None,
        description="Additional preferences for replanning (e.g., prefer indoor, avoid crowds)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "system_proactive",
                "trigger_type": "weather",
                "trigger_details": "Heavy rain expected from 2PM-6PM",
                "current_gps_location": {
                    "latitude": 35.6762,
                    "longitude": 139.6503,
                    "accuracy_meters": 10.0
                },
                "affected_day": 2,
                "user_preferences": {
                    "prefer_indoor": True,
                    "max_walking_distance_km": 1.0
                }
            }
        }
    )


class ChangedActivity(BaseModel):
    """Represents a changed activity in the replan."""

    original_activity: dict = Field(..., description="The original activity that was changed")
    new_activity: dict = Field(..., description="The replacement activity")
    reason: str = Field(..., description="Why this activity was changed")
    impact_level: str = Field(
        ...,
        description="Impact level: minor, moderate, major",
    )


class ReplanChange(BaseModel):
    """A single change in the replan."""

    change_type: str = Field(
        ...,
        description="Type of change: substitution, rescheduled, removed, added, route_updated",
    )
    day_number: int = Field(..., ge=1)
    original_item: dict | None = Field(None, description="Original item before change")
    new_item: dict | None = Field(None, description="New/modified item")
    reason: str = Field(..., description="Reason for this change")
    transit_updated: bool = Field(
        default=False,
        description="Whether transit details were updated",
    )
    affiliate_links_updated: bool = Field(
        default=False,
        description="Whether affiliate links were updated",
    )


class ReplanSummary(BaseModel):
    """Summary of replan changes."""

    total_changes: int = Field(..., ge=0)
    activities_substituted: int = Field(default=0, ge=0)
    activities_rescheduled: int = Field(default=0, ge=0)
    activities_removed: int = Field(default=0, ge=0)
    activities_added: int = Field(default=0, ge=0)
    routes_updated: int = Field(default=0, ge=0)
    estimated_time_saved_minutes: int = Field(default=0)
    estimated_cost_difference: Decimal = Field(default=Decimal("0"))


class ReplanResponse(BaseModel):
    """Response schema for replan request."""

    itinerary_id: UUID = Field(..., description="ID of the itinerary")
    task_id: str = Field(..., description="Celery task ID for tracking")
    status: str = Field(..., description="Replan status: processing, completed, failed")
    message: str = Field(..., description="Human-readable status message")
    websocket_url: str = Field(..., description="WebSocket URL for real-time updates")

    # Version info
    version: int = Field(..., description="New version number after replan")
    previous_version: int = Field(..., description="Previous version number")

    # Changes summary (populated when complete)
    summary: ReplanSummary | None = None
    changes: list[ReplanChange] | None = Field(
        None,
        description="List of changes made (highlighted for frontend)",
    )

    # Alert info for proactive replans
    is_critical: bool = Field(
        default=False,
        description="Whether this is a critical alert requiring immediate attention",
    )
    alert_message: str | None = Field(
        None,
        description="Alert message for WebSocket notification",
    )

    created_at: datetime


class ReplanCompletedResponse(BaseModel):
    """Full response when replan is completed."""

    itinerary_id: UUID
    version: int
    previous_version: int
    status: str = "completed"

    # The updated itinerary data
    updated_data: dict = Field(..., description="Complete updated itinerary (AIFullItinerary)")

    # Change details
    summary: ReplanSummary
    changes: list[ReplanChange]

    # For frontend highlighting
    changed_activity_ids: list[str] = Field(
        default_factory=list,
        description="IDs of activities that changed (for UI highlighting)",
    )

    completed_at: datetime


class ProactiveAlertPayload(BaseModel):
    """WebSocket payload for proactive system alerts."""

    alert_type: str = Field(..., description="Type: weather_warning, traffic_alert, crowd_alert")
    itinerary_id: UUID
    severity: str = Field(..., description="Severity: info, warning, critical")
    title: str = Field(..., max_length=100)
    message: str = Field(..., max_length=500)

    # Affected items
    affected_day: int | None = None
    affected_activities: list[str] | None = None

    # Action
    action_url: str | None = Field(None, description="Deep link to replan action")
    action_text: str | None = Field(None, description="CTA text like 'View alternatives'")

    # Metadata
    trigger_type: ReplanTriggerType
    timestamp: datetime
    expires_at: datetime | None = None


class VersionHistoryEntry(BaseModel):
    """Single entry in version history."""

    version: int = Field(..., description="Version number")
    timestamp: str | None = Field(None, description="When this version was created")
    reason: str | None = Field(None, description="Reason for change (replan, etc.)")
    changes_count: int = Field(default=0, description="Number of changes in this version")


class VersionHistoryResponse(BaseModel):
    """Response schema for version history endpoint."""

    itinerary_id: UUID = Field(..., description="ID of the itinerary")
    current_version: int = Field(..., description="Current active version number")
    versions: list[VersionHistoryEntry] = Field(
        default_factory=list,
        description="List of previous versions",
    )
    last_replan_at: datetime | None = Field(
        None,
        description="When the last replan occurred",
    )


# ============ AI Structured Output Schemas (LangGraph) ============
# These schemas define the structured output format for the Intelligence Engine.
# They ensure AI outputs are consistent and can be directly consumed by Mobile/Web UIs.


class TransitMode(str, Enum):
    """Transit modes for getting between locations."""

    WALK = "walk"
    SUBWAY = "subway"
    BUS = "bus"
    TRAIN = "train"
    TRAM = "tram"
    TAXI = "taxi"
    RIDESHARE = "rideshare"  # Grab, Uber, etc.
    FERRY = "ferry"
    CABLE_CAR = "cable_car"
    DRIVE = "drive"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"


class BookingType(str, Enum):
    """Types of bookable items."""

    FLIGHT = "flight"
    HOTEL = "hotel"
    TRAIN = "train"
    BUS = "bus"
    ACTIVITY = "activity"
    TOUR = "tour"
    CAR_RENTAL = "car_rental"
    TRANSFER = "transfer"
    INSURANCE = "insurance"


class WeatherCondition(str, Enum):
    """Weather conditions for planning."""

    SUNNY = "sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    WINDY = "windy"
    HOT = "hot"
    COLD = "cold"


class TransitDetail(BaseModel):
    """
    Transit information for getting from one activity to the next.
    
    Used by Mobile/Web to show directions between activities.
    """

    mode: TransitMode = Field(
        ...,
        description="Mode of transportation",
    )
    duration_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated travel time in minutes",
    )
    distance_meters: int | None = Field(
        None,
        ge=0,
        description="Distance in meters (if applicable)",
    )
    line_name: str | None = Field(
        None,
        max_length=100,
        description="Transit line name (e.g., 'BTS Sukhumvit', 'JR Yamanote')",
    )
    line_color: str | None = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Line color in hex format for UI display",
    )
    station_name: str | None = Field(
        None,
        max_length=200,
        description="Departure station/stop name",
    )
    destination_station: str | None = Field(
        None,
        max_length=200,
        description="Arrival station/stop name",
    )
    exit_number: str | None = Field(
        None,
        max_length=20,
        description="Exit number at destination station (e.g., 'Exit 4', '出口A')",
    )
    fare_amount: Decimal | None = Field(
        None,
        ge=0,
        description="Transit fare amount",
    )
    fare_currency: str = Field(
        default="THB",
        min_length=3,
        max_length=3,
    )
    instructions: str | None = Field(
        None,
        max_length=500,
        description="Human-readable transit instructions",
    )
    polyline: str | None = Field(
        None,
        description="Encoded polyline for map rendering (Google format)",
    )


class WeatherContext(BaseModel):
    """
    Weather information for activity planning.
    
    Helps users prepare for conditions at each activity.
    """

    condition: WeatherCondition = Field(
        ...,
        description="Expected weather condition",
    )
    temperature_celsius: float = Field(
        ...,
        ge=-50,
        le=60,
        description="Expected temperature in Celsius",
    )
    temperature_fahrenheit: float = Field(
        ...,
        ge=-58,
        le=140,
        description="Expected temperature in Fahrenheit",
    )
    humidity_percent: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Humidity percentage",
    )
    precipitation_chance: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Chance of precipitation (%)",
    )
    uv_index: int | None = Field(
        None,
        ge=0,
        le=11,
        description="UV index (0-11 scale)",
    )
    wind_speed_kmh: float | None = Field(
        None,
        ge=0,
        description="Wind speed in km/h",
    )
    advisory: str | None = Field(
        None,
        max_length=300,
        description="Weather advisory or recommendation (e.g., 'Bring umbrella', 'Stay hydrated')",
    )
    icon: str | None = Field(
        None,
        max_length=50,
        description="Weather icon identifier for UI",
    )

    # Fallback indicator
    is_estimated: bool = Field(
        default=False,
        description="True if this weather data is AI-estimated due to API failure",
    )
    data_source: str | None = Field(
        None,
        description="Data source (e.g., 'openweathermap', 'ai_fallback')",
    )


class LocationInfo(BaseModel):
    """Detailed location information with coordinates."""

    name: str = Field(..., max_length=255, description="Location/venue name")
    address: str | None = Field(None, max_length=500, description="Full address")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    google_place_id: str | None = Field(None, max_length=255)
    google_maps_url: str | None = Field(None, description="Google Maps deep link")
    phone: str | None = Field(None, max_length=30)
    website: str | None = Field(None, max_length=500)
    rating: float | None = Field(None, ge=0, le=5, description="Venue rating (0-5)")
    review_count: int | None = Field(None, ge=0)
    price_level: int | None = Field(
        None,
        ge=1,
        le=4,
        description="Price level (1=cheap, 4=expensive)",
    )
    opening_hours: list[str] | None = Field(
        None,
        description="Opening hours by day of week",
    )
    photos: list[str] | None = Field(
        None,
        description="Photo URLs for the location",
    )

    # Images from Google Image Search
    images: list[LocationImage] | None = Field(
        None,
        description="Images of this location from Google Image Search",
    )
    primary_image_url: str | None = Field(
        None,
        description="Primary image URL for thumbnail display",
    )
    primary_thumbnail_url: str | None = Field(
        None,
        description="Primary thumbnail URL for list views",
    )


class AIActivity(BaseModel):
    """
    AI-generated activity with full context for Mobile/Web rendering.
    
    This is the core building block of the itinerary that the AI generates.
    Includes all information needed to render a rich activity card.
    """

    title: str = Field(..., min_length=1, max_length=255, description="Activity name")
    description: str = Field(
        ...,
        max_length=1000,
        description="Rich description of the activity",
    )
    category: ActivityCategory = Field(
        default=ActivityCategory.SIGHTSEEING,
        description="Activity category for filtering/icons",
    )

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        """Convert uppercase enum names to lowercase enum values."""
        if isinstance(v, str):
            # Convert to lowercase for matching enum values
            v_lower = v.lower()
            # Valid enum values
            valid_values = ["transportation", "accommodation", "dining", "sightseeing", "entertainment", "shopping", "other"]
            if v_lower in valid_values:
                return v_lower
            # Default to sightseeing for unknown categories
            return "sightseeing"
        return v

    # Timing
    start_time: time = Field(..., description="Activity start time")
    end_time: time = Field(..., description="Activity end time")
    duration_minutes: int = Field(..., ge=1, description="Duration in minutes")

    # Location
    location: LocationInfo = Field(..., description="Full location details")

    # Cost
    estimated_cost: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Estimated cost for this activity",
    )
    cost_currency: str = Field(default="THB", min_length=3, max_length=3)
    cost_notes: str | None = Field(
        None,
        max_length=200,
        description="Notes about cost (e.g., 'Free admission on Wednesdays')",
    )

    # Context
    weather_context: WeatherContext | None = Field(
        None,
        description="Weather forecast for this activity time",
    )
    local_tips: list[str] | None = Field(
        None,
        description="Local tips and recommendations",
    )
    best_for: list[str] | None = Field(
        None,
        description="Who this activity is best for (e.g., 'families', 'couples')",
    )

    # Navigation to next activity
    transit_to_next: TransitDetail | None = Field(
        None,
        description="How to get to the next activity (null for last activity of day)",
    )

    # Metadata
    requires_booking: bool = Field(
        default=False,
        description="Whether advance booking is recommended",
    )
    booking_url: str | None = Field(None, description="Direct booking URL if available")
    tags: list[str] | None = Field(None, description="Tags for filtering/search")
    accessibility_info: str | None = Field(
        None,
        max_length=300,
        description="Accessibility information",
    )

    # Activity images
    activity_images: list[LocationImage] | None = Field(
        None,
        description="Images related to this activity",
    )
    hero_image_url: str | None = Field(
        None,
        description="Hero image URL for activity card",
    )

    # Fallback indicator
    is_estimated: bool = Field(
        default=False,
        description="True if this activity data is AI-estimated due to API failure",
    )
    data_source: str | None = Field(
        None,
        description="Data source (e.g., 'google_places', 'ai_fallback')",
    )


class BookingOption(BaseModel):
    """
    Affiliate booking option from Travelpayouts or other providers.
    
    Used to show bookable flights, hotels, and other services.
    """

    booking_type: BookingType = Field(..., description="Type of booking")
    provider: str = Field(
        ...,
        max_length=100,
        description="Provider name (e.g., 'Expedia', 'Booking.com', 'Thai Airways')",
    )
    provider_logo: str | None = Field(None, description="Provider logo URL")

    # Pricing
    price: Decimal = Field(..., ge=0, description="Total price")
    original_price: Decimal | None = Field(
        None,
        ge=0,
        description="Original price before discount (if applicable)",
    )
    currency: str = Field(default="THB", min_length=3, max_length=3)
    price_per_night: Decimal | None = Field(
        None,
        ge=0,
        description="Per-night price for hotels",
    )

    # Details
    title: str = Field(..., max_length=255, description="Booking item title")
    description: str | None = Field(None, max_length=500)
    rating: float | None = Field(None, ge=0, le=5, description="Rating if available")
    review_count: int | None = Field(None, ge=0)

    # Flight-specific
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    departure_airport: str | None = Field(None, max_length=5)
    arrival_airport: str | None = Field(None, max_length=5)
    airline: str | None = Field(None, max_length=100)
    flight_number: str | None = Field(None, max_length=20)
    stops: int | None = Field(None, ge=0, description="Number of stops (0=direct)")
    cabin_class: str | None = Field(
        None,
        description="Cabin class (economy, business, first)",
    )

    # Hotel-specific
    hotel_stars: int | None = Field(None, ge=1, le=5)
    check_in_date: date | None = None
    check_out_date: date | None = None
    room_type: str | None = Field(None, max_length=100)
    amenities: list[str] | None = None

    # Affiliate
    affiliate_url: str = Field(
        ...,
        description="Travelpayouts or partner affiliate URL",
    )
    affiliate_id: str | None = Field(None, description="Affiliate tracking ID")
    deeplink: str | None = Field(
        None,
        description="App deeplink for mobile",
    )

    # Metadata
    is_refundable: bool | None = None
    cancellation_policy: str | None = Field(None, max_length=300)
    valid_until: datetime | None = Field(
        None,
        description="Price validity expiration",
    )

    # Fallback indicator
    is_estimated: bool = Field(
        default=False,
        description="True if this is AI-estimated data due to API failure",
    )
    data_source: str | None = Field(
        None,
        description="Data source (e.g., 'amadeus', 'travelpayouts', 'ai_fallback')",
    )


class AIDailyPlan(BaseModel):
    """
    AI-generated daily plan containing activities for one day.
    
    This groups activities by day for easy calendar rendering.
    Includes location context and booking recommendations for realistic trip planning.
    """

    day_number: int = Field(..., ge=1, description="Day number in the trip (1-indexed)")
    plan_date: date = Field(..., description="Calendar date for this day")
    title: str = Field(
        ...,
        max_length=100,
        description="Day title (e.g., 'Exploring Old Town', 'Beach Day')",
    )
    summary: str | None = Field(
        None,
        max_length=500,
        description="Brief summary of the day's plan",
    )
    
    # Location context - where you are this day
    location_city: str | None = Field(
        None,
        max_length=100,
        description="City for this day (e.g., 'Tokyo', 'Osaka')",
    )
    location_country: str | None = Field(
        None,
        max_length=100,
        description="Country for this day",
    )
    
    # Travel day indicators
    is_travel_day: bool = Field(
        default=False,
        description="True if this day involves significant travel (city/country change)",
    )
    travel_from: str | None = Field(
        None,
        max_length=100,
        description="Origin city if traveling this day",
    )
    travel_to: str | None = Field(
        None,
        max_length=100,
        description="Destination city if traveling this day",
    )

    @field_validator("plan_date", mode="before")
    @classmethod
    def normalize_plan_date(cls, v, info):
        """Accept 'date' field as alias for 'plan_date'."""
        # If None, check if 'date' was provided in data
        if v is None and info.data.get("date"):
            return info.data["date"]
        return v

    def __init__(self, **data):
        # Handle 'date' field as alias for 'plan_date'
        if "date" in data and "plan_date" not in data:
            data["plan_date"] = data.pop("date")
        super().__init__(**data)

    # Activities
    activities: list[AIActivity] = Field(
        ...,
        min_length=1,
        description="Ordered list of activities for this day",
    )

    # Daily totals
    total_cost: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total estimated cost for the day",
    )
    total_walking_minutes: int = Field(
        default=0,
        ge=0,
        description="Total walking time in minutes",
    )
    total_transit_minutes: int = Field(
        default=0,
        ge=0,
        description="Total transit time in minutes",
    )

    # Weather
    weather_summary: WeatherContext | None = Field(
        None,
        description="Overall weather forecast for the day",
    )

    # Notes
    notes: str | None = Field(
        None,
        max_length=500,
        description="Special notes or reminders for this day",
    )
    meal_recommendations: list[str] | None = Field(
        None,
        description="Recommended restaurants/food for the day",
    )
    
    # ========== Daily Booking Recommendations ==========
    # These are context-aware recommendations for each specific day
    
    # Flight recommendations (shown on travel days)
    recommended_flights: list["BookingOption"] | None = Field(
        None,
        description="Flight options if traveling to another city/country this day",
    )
    
    # Hotel recommendation for tonight
    recommended_hotel: "BookingOption | None" = Field(
        None,
        description="Recommended hotel for staying tonight in this city",
    )
    
    # Bookable activities for this day
    bookable_activities: list["BookingOption"] | None = Field(
        None,
        description="Activities/tours that can be booked for this day",
    )
    
    # Daily tips
    daily_tips: list[str] | None = Field(
        None,
        description="Tips specific to this day (e.g., 'Book Skytree tickets in advance')",
    )


class AIFullItinerary(BaseModel):
    """
    Complete AI-generated itinerary with all days, bookings, and summaries.
    
    This is the main output schema from the LangGraph Intelligence Engine.
    Mobile/Web can render the entire trip from this single response.
    """

    # Basic info
    title: str = Field(..., max_length=255, description="Itinerary title")
    destination: str = Field(..., max_length=255, description="Main destination")
    destination_country: str = Field(..., max_length=100)
    destination_city: str = Field(..., max_length=100)

    # Dates
    start_date: date
    end_date: date
    duration_days: int = Field(..., ge=1, description="Total trip duration in days")

    # Travelers
    traveler_count: int = Field(default=1, ge=1)
    trip_type: str | None = Field(
        None,
        description="Trip type (solo, couple, family, group)",
    )

    # Daily plans
    daily_plans: list[AIDailyPlan] = Field(
        ...,
        min_length=1,
        description="Complete daily plans for the trip",
    )

    # Destination images
    destination_images: list[LocationImage] | None = Field(
        None,
        description="Images of the main destination",
    )
    cover_image_url: str | None = Field(
        None,
        description="Main cover image URL for itinerary",
    )

    # Booking options
    flight_options: list[BookingOption] | None = Field(
        None,
        description="Available flight bookings from Travelpayouts",
    )
    hotel_options: list[BookingOption] | None = Field(
        None,
        description="Available hotel bookings",
    )
    activity_bookings: list[BookingOption] | None = Field(
        None,
        description="Bookable activities and tours",
    )

    # Totals
    total_estimated_cost: Decimal = Field(
        ...,
        ge=0,
        description="Total estimated trip cost",
    )
    cost_breakdown: dict[str, Decimal] | None = Field(
        None,
        description="Cost breakdown by category (flights, hotels, activities, food, transport)",
    )
    currency: str = Field(default="THB", min_length=3, max_length=3)

    # Weather
    weather_summary: str | None = Field(
        None,
        max_length=500,
        description="Overall weather summary for the trip period",
    )
    best_time_to_visit: str | None = Field(
        None,
        max_length=200,
        description="Note about best time to visit",
    )
    packing_suggestions: list[str] | None = Field(
        None,
        description="Suggested items to pack based on weather/activities",
    )

    # Practical info
    visa_info: str | None = Field(
        None,
        max_length=500,
        description="Visa requirements summary",
    )
    local_currency: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=100)
    emergency_contacts: dict[str, str] | None = Field(
        None,
        description="Emergency contact numbers",
    )
    local_customs: list[str] | None = Field(
        None,
        description="Important local customs to know",
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When the itinerary was generated",
    )
    confidence_score: float | None = Field(
        None,
        ge=0,
        le=1,
        description="AI confidence score for this itinerary",
    )
    sources_used: list[str] | None = Field(
        None,
        description="Data sources used (Amadeus, Google Maps, Weather API, etc.)",
    )

    # Fallback indicators
    has_estimated_data: bool = Field(
        default=False,
        description="True if any data was AI-estimated due to API failures",
    )
    estimated_data_sources: list[str] | None = Field(
        None,
        description="List of data sources that used AI fallback (e.g., ['flights', 'weather'])",
    )
    api_errors: list[dict] | None = Field(
        None,
        description="List of API errors encountered during generation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "7-Day Tokyo Adventure",
                "destination": "Tokyo, Japan",
                "destination_country": "Japan",
                "destination_city": "Tokyo",
                "start_date": "2025-04-01",
                "end_date": "2025-04-07",
                "duration_days": 7,
                "traveler_count": 2,
                "trip_type": "couple",
                "total_estimated_cost": 150000,
                "currency": "THB",
                "weather_summary": "Spring weather with cherry blossoms. Expect mild temperatures (15-20°C) with occasional rain.",
            }
        }
    )

