"""
AiGo Backend - LangGraph Planner Workflow
Intelligence Engine for AI-powered itinerary generation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.domains.itinerary.schemas import (
    AIActivity,
    AIDailyPlan,
    AIFullItinerary,
    BookingOption,
    BookingType,
    LocationInfo,
    TransitDetail,
    TransitMode,
    WeatherCondition as WeatherConditionEnum,
    WeatherContext,
)
from app.domains.itinerary.tools import (
    AmadeusTool,
    GoogleMapsTransitTool,
    TravelpayoutsTool,
    WeatherTool,
)

logger = logging.getLogger(__name__)


# ============ Agent State Definition ============


class PlannerStep(str, Enum):
    """Steps in the planning workflow."""

    INTENT_EXTRACTION = "intent_extraction"
    DATA_GATHERING = "data_gathering"
    ITINERARY_GENERATION = "itinerary_generation"
    ROUTE_OPTIMIZATION = "route_optimization"
    MONETIZATION = "monetization"
    FINALIZATION = "finalization"
    ERROR = "error"


class ExtractedIntent(BaseModel):
    """Extracted travel intent from user prompt."""

    destination_city: str = Field(..., description="Main destination city")
    destination_country: str = Field(..., description="Destination country")
    origin_city: str | None = Field(None, description="Origin city if mentioned")
    start_date: date = Field(..., description="Trip start date")
    end_date: date = Field(..., description="Trip end date")
    duration_days: int = Field(..., description="Trip duration in days")
    travelers_count: int = Field(default=1, description="Number of travelers")
    trip_type: str | None = Field(None, description="Trip type: solo, couple, family, group")
    budget_amount: Decimal | None = Field(None, description="Total budget if specified")
    budget_currency: str | None = Field(default="THB", description="Budget currency")
    interests: list[str] | None = Field(default_factory=list, description="Travel interests")
    pace_preference: str | None = Field(default="moderate", description="Travel pace: relaxed, moderate, intensive")
    accommodation_preference: str | None = Field(None, description="Preferred accommodation type")
    special_requirements: list[str] | None = Field(default_factory=list, description="Special needs or requirements")
    must_visit_places: list[str] | None = Field(default_factory=list, description="Must-visit attractions")
    dietary_restrictions: list[str] | None = Field(default_factory=list, description="Food restrictions")

    @model_validator(mode="before")
    @classmethod
    def handle_none_values(cls, data: dict) -> dict:
        """Handle None values for fields with defaults."""
        if isinstance(data, dict):
            # List fields - convert None to empty list
            list_fields = ["interests", "special_requirements", "must_visit_places", "dietary_restrictions"]
            for field in list_fields:
                if field in data and data[field] is None:
                    data[field] = []
            
            # String fields with defaults - convert None to default
            if data.get("pace_preference") is None:
                data["pace_preference"] = "moderate"
            if data.get("budget_currency") is None:
                data["budget_currency"] = "THB"
            
            # Int field with default - convert None to default
            if data.get("travelers_count") is None:
                data["travelers_count"] = 1
        
        return data


class GatheredData(BaseModel):
    """Data gathered from external APIs."""

    flights: list[dict] = Field(default_factory=list)
    hotels: list[dict] = Field(default_factory=list)
    weather_forecast: dict | None = None
    attractions: list[dict] = Field(default_factory=list)
    restaurants: list[dict] = Field(default_factory=list)


class AgentState(TypedDict):
    """
    State for the LangGraph planning workflow.
    
    Tracks all data through the itinerary generation process.
    """

    # Input
    user_prompt: str
    itinerary_id: str
    user_id: str | None
    preferences: dict | None

    # Messages for LLM conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Current step
    current_step: PlannerStep
    step_progress: int
    step_message: str

    # Extracted data
    intent: ExtractedIntent | None
    gathered_data: GatheredData | None

    # Generated content
    daily_plans: list[AIDailyPlan]
    booking_options: list[BookingOption]

    # Final output
    final_itinerary: AIFullItinerary | None

    # Error handling
    error: str | None
    retry_count: int
    should_retry: bool

    # Progress callback
    progress_callback: Any | None


# ============ LLM Configuration ============


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Get configured ChatOpenAI instance."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Prompts ============


INTENT_EXTRACTION_PROMPT = """You are an expert travel planner assistant. Extract travel intent from the user's request.

Today's date: {today_date}

User Request:
{user_prompt}

User Preferences (if provided):
{preferences}

Extract the following information in JSON format:
- destination_city: The main city to visit
- destination_country: The country
- origin_city: Starting city (if mentioned, otherwise null)
- start_date: Trip start date (YYYY-MM-DD format, estimate if not specified)
- end_date: Trip end date (YYYY-MM-DD format)
- duration_days: Number of days
- travelers_count: Number of travelers (default 1)
- trip_type: "solo", "couple", "family", or "group"
- budget_amount: Numeric budget amount
- budget_currency: Currency code (default "THB")
- interests: List of interests like ["food", "culture", "adventure", "shopping", "nightlife", "nature", "photography"]
- pace_preference: "relaxed", "moderate", or "intensive"
- accommodation_preference: "budget", "mid-range", "luxury", or null
- special_requirements: Any special needs
- must_visit_places: Specific places mentioned
- dietary_restrictions: Any food restrictions

Be intelligent about inferring dates:
- If user says "next week", calculate from today
- If user says "5 days", set appropriate start/end dates
- Default to 30 days from now if no date specified

Return ONLY valid JSON, no markdown."""


ITINERARY_GENERATION_PROMPT = """You are an expert travel planner creating a detailed day-by-day itinerary.

Trip Details:
- Destination: {destination_city}, {destination_country}
- Dates: {start_date} to {end_date} ({duration_days} days)
- Budget: {budget_amount} {budget_currency}
- Travelers: {travelers_count} ({trip_type})
- Interests: {interests}
- Pace: {pace_preference}

Weather Forecast:
{weather_summary}

Available Attractions:
{attractions}

Flight Options:
{flights}

Hotel Options:
{hotels}

Create a detailed daily itinerary with:
1. Logical geographical grouping (minimize travel between activities)
2. Appropriate timing for each activity (consider opening hours)
3. Meal breaks at local restaurants
4. Weather-appropriate activities (indoor alternatives for rainy days)
5. Mix of {interests} throughout the trip

For each activity include:
- Specific time (HH:MM format)
- Activity name and description
- Location with address
- Duration in minutes
- Estimated cost
- Why this activity fits the traveler's interests

Return a JSON array of daily plans."""


ACTIVITY_DETAIL_PROMPT = """Enhance this activity with detailed information:

Activity: {activity_name}
Location: {location}
City: {city}
Weather: {weather}

Provide:
1. A compelling 2-3 sentence description
2. Local tips for visitors
3. Best time to visit
4. Estimated cost range
5. Who this activity is best for

Return JSON with: description, local_tips (array), best_time, cost_range, best_for (array)"""


# ============ Node Functions ============


async def intent_extraction_node(state: AgentState) -> dict:
    """
    Extract travel intent from user prompt using LLM.
    
    This node parses natural language into structured travel parameters.
    """
    logger.info(f"Starting intent extraction for itinerary {state['itinerary_id']}")

    # Update progress
    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.INTENT_EXTRACTION,
            progress=10,
            message="🔍 Understanding your travel request...",
        )

    llm = get_llm(temperature=0.3)  # Lower temperature for extraction

    prompt = ChatPromptTemplate.from_template(INTENT_EXTRACTION_PROMPT)
    
    today = date.today()
    preferences_str = str(state.get("preferences", {})) if state.get("preferences") else "None provided"

    messages = prompt.format_messages(
        today_date=today.isoformat(),
        user_prompt=state["user_prompt"],
        preferences=preferences_str,
    )

    try:
        response = await llm.ainvoke(messages)

        # Parse JSON response
        import json
        content = response.content.strip()
        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        intent_data = json.loads(content)
        intent = ExtractedIntent(**intent_data)

        logger.info(f"Extracted intent: {intent.destination_city}, {intent.duration_days} days")

        return {
            "intent": intent,
            "current_step": PlannerStep.DATA_GATHERING,
            "step_progress": 20,
            "step_message": f"Planning {intent.duration_days}-day trip to {intent.destination_city}",
            "messages": [
                HumanMessage(content=state["user_prompt"]),
                AIMessage(content=f"I'll plan a {intent.duration_days}-day trip to {intent.destination_city}, {intent.destination_country}"),
            ],
        }

    except Exception as e:
        logger.error(f"Intent extraction failed: {e}")
        return {
            "error": f"Failed to understand request: {str(e)}",
            "current_step": PlannerStep.ERROR,
            "should_retry": True,
            "retry_count": state.get("retry_count", 0) + 1,
        }


async def data_gathering_node(state: AgentState) -> dict:
    """
    Gather data from external APIs in parallel with fallback support.
    
    Fetches flights, hotels, weather, and attractions concurrently.
    If any API fails, uses AI-generated fallback data with is_estimated flag.
    """
    intent = state["intent"]
    if not intent:
        return {"error": "No intent extracted", "current_step": PlannerStep.ERROR}

    logger.info(f"Gathering data for {intent.destination_city}")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.DATA_GATHERING,
            progress=30,
            message="📡 Gathering travel data from multiple sources...",
        )

    gathered = GatheredData()
    api_errors: list[dict] = []  # Track errors for reporting

    # Prepare parallel tasks with error handling
    tasks = []

    # Flight search (if origin provided)
    if intent.origin_city:
        tasks.append(_search_flights_with_fallback(intent))
    else:
        async def _noop():
            return None
        tasks.append(_noop())

    # Hotel search
    tasks.append(_search_hotels_with_fallback(intent))

    # Weather forecast
    tasks.append(_get_weather_with_fallback(intent))

    # Attractions search
    tasks.append(_search_attractions_with_fallback(intent))

    # Execute in parallel - all wrapped with error handling
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results and track any errors
    # Result 0: Flights
    if intent.origin_city:
        if isinstance(results[0], Exception):
            logger.error(f"Flight search completely failed: {results[0]}")
            api_errors.append({"tool": "amadeus_flights", "error": str(results[0])})
        elif results[0]:
            flight_result = results[0]
            gathered.flights = flight_result.get("data", []) if isinstance(flight_result, dict) else []
            if flight_result.get("is_estimated"):
                api_errors.append({
                    "tool": "amadeus_flights",
                    "error": flight_result.get("error_message"),
                    "fallback_used": True,
                })

    # Result 1: Hotels
    if isinstance(results[1], Exception):
        logger.error(f"Hotel search completely failed: {results[1]}")
        api_errors.append({"tool": "amadeus_hotels", "error": str(results[1])})
    elif results[1]:
        hotel_result = results[1]
        gathered.hotels = hotel_result.get("data", []) if isinstance(hotel_result, dict) else []
        if hotel_result.get("is_estimated"):
            api_errors.append({
                "tool": "amadeus_hotels",
                "error": hotel_result.get("error_message"),
                "fallback_used": True,
            })

    # Result 2: Weather
    if isinstance(results[2], Exception):
        logger.error(f"Weather fetch completely failed: {results[2]}")
        api_errors.append({"tool": "weather_api", "error": str(results[2])})
    elif results[2]:
        weather_result = results[2]
        gathered.weather_forecast = weather_result.get("data") if isinstance(weather_result, dict) else weather_result
        if isinstance(weather_result, dict) and weather_result.get("is_estimated"):
            api_errors.append({
                "tool": "weather_api",
                "error": weather_result.get("error_message"),
                "fallback_used": True,
            })

    # Result 3: Attractions
    if isinstance(results[3], Exception):
        logger.error(f"Attractions search completely failed: {results[3]}")
        api_errors.append({"tool": "google_places", "error": str(results[3])})
    elif results[3]:
        attractions_result = results[3]
        gathered.attractions = attractions_result.get("data", []) if isinstance(attractions_result, dict) else []
        if attractions_result.get("is_estimated"):
            api_errors.append({
                "tool": "google_places",
                "error": attractions_result.get("error_message"),
                "fallback_used": True,
            })

    logger.info(
        f"Gathered: {len(gathered.flights)} flights, "
        f"{len(gathered.hotels)} hotels, "
        f"{len(gathered.attractions)} attractions "
        f"(API errors: {len(api_errors)})"
    )

    # Determine message based on fallback usage
    if api_errors:
        fallback_count = sum(1 for e in api_errors if e.get("fallback_used"))
        if fallback_count > 0:
            step_message = f"Data collected! (Some estimates used due to API issues)"
        else:
            step_message = "Data collected with some limitations. Generating itinerary..."
    else:
        step_message = "Data collected! Generating your personalized itinerary..."

    return {
        "gathered_data": gathered,
        "current_step": PlannerStep.ITINERARY_GENERATION,
        "step_progress": 50,
        "step_message": step_message,
        # Store API errors in state for potential UI display
        "api_errors": api_errors if api_errors else None,
    }


async def _search_flights_with_fallback(intent: ExtractedIntent) -> dict:
    """Search for flights using Amadeus with fallback."""
    from app.domains.itinerary.tools.fallback import (
        generate_flight_fallback,
        tool_health,
        classify_error,
    )
    
    tool_name = "amadeus_flights"
    
    # Check if we should skip directly to fallback
    if tool_health.should_use_fallback(tool_name):
        logger.warning(f"Skipping {tool_name} due to repeated failures, using fallback")
        result = await generate_flight_fallback(
            origin=intent.origin_city[:3].upper() if intent.origin_city else "BKK",
            destination=_get_airport_code(intent.destination_city),
            departure_date=intent.start_date.isoformat(),
            return_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
        )
        return {
            "data": result.data.get("offers", [])[:5],
            "is_estimated": True,
            "error_message": "Service temporarily unavailable",
        }
    
    try:
        tool = AmadeusTool.flight_search
        result = await tool._arun(
            origin=intent.origin_city[:3].upper() if intent.origin_city else "BKK",
            destination=_get_airport_code(intent.destination_city),
            departure_date=intent.start_date.isoformat(),
            return_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
        )
        tool_health.record_success(tool_name)
        return {
            "data": result.get("offers", [])[:5],
            "is_estimated": False,
        }
    except Exception as e:
        logger.warning(f"Flight search failed: {e}, using fallback")
        tool_health.record_failure(tool_name, e)
        
        # Generate fallback data
        result = await generate_flight_fallback(
            origin=intent.origin_city[:3].upper() if intent.origin_city else "BKK",
            destination=_get_airport_code(intent.destination_city),
            departure_date=intent.start_date.isoformat(),
            return_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
            error=e,
        )
        return {
            "data": result.data.get("offers", [])[:5] if result.data else [],
            "is_estimated": True,
            "error_message": str(e),
            "error_type": classify_error(e),
        }


async def _search_hotels_with_fallback(intent: ExtractedIntent) -> dict:
    """Search for hotels using Amadeus with fallback."""
    from app.domains.itinerary.tools.fallback import (
        generate_hotel_fallback,
        tool_health,
        classify_error,
    )
    
    tool_name = "amadeus_hotels"
    
    # Check if we should skip directly to fallback
    if tool_health.should_use_fallback(tool_name):
        logger.warning(f"Skipping {tool_name} due to repeated failures, using fallback")
        result = await generate_hotel_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            check_in_date=intent.start_date.isoformat(),
            check_out_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
        )
        return {
            "data": result.data.get("offers", [])[:10],
            "is_estimated": True,
            "error_message": "Service temporarily unavailable",
        }
    
    try:
        tool = AmadeusTool.hotel_search
        result = await tool._arun(
            city_code=_get_city_code(intent.destination_city),
            check_in_date=intent.start_date.isoformat(),
            check_out_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
        )
        tool_health.record_success(tool_name)
        return {
            "data": result.get("offers", [])[:10],
            "is_estimated": False,
        }
    except Exception as e:
        logger.warning(f"Hotel search failed: {e}, using fallback")
        tool_health.record_failure(tool_name, e)
        
        # Generate fallback data
        result = await generate_hotel_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            check_in_date=intent.start_date.isoformat(),
            check_out_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
            error=e,
        )
        return {
            "data": result.data.get("offers", [])[:10] if result.data else [],
            "is_estimated": True,
            "error_message": str(e),
            "error_type": classify_error(e),
        }


async def _get_weather_with_fallback(intent: ExtractedIntent) -> dict:
    """Get weather forecast with fallback."""
    from app.domains.itinerary.tools.fallback import (
        generate_weather_fallback,
        tool_health,
        classify_error,
    )
    
    tool_name = "weather_api"
    
    # Check if we should skip directly to fallback
    if tool_health.should_use_fallback(tool_name):
        logger.warning(f"Skipping {tool_name} due to repeated failures, using fallback")
        result = await generate_weather_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            start_date=intent.start_date.isoformat(),
            end_date=intent.end_date.isoformat(),
        )
        return {
            "data": result.data,
            "is_estimated": True,
            "error_message": "Service temporarily unavailable",
        }
    
    try:
        tool = WeatherTool.forecast
        result = await tool._arun(
            location=intent.destination_city,
            start_date=intent.start_date.isoformat(),
            end_date=intent.end_date.isoformat(),
            units="metric",
        )
        tool_health.record_success(tool_name)
        return {
            "data": result,
            "is_estimated": False,
        }
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}, using fallback")
        tool_health.record_failure(tool_name, e)
        
        # Generate fallback data
        result = await generate_weather_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            start_date=intent.start_date.isoformat(),
            end_date=intent.end_date.isoformat(),
            error=e,
        )
        return {
            "data": result.data,
            "is_estimated": True,
            "error_message": str(e),
            "error_type": classify_error(e),
        }


async def _search_attractions_with_fallback(intent: ExtractedIntent) -> dict:
    """Search for attractions using Google Maps with fallback."""
    from app.domains.itinerary.tools.fallback import (
        generate_attractions_fallback,
        tool_health,
        classify_error,
    )
    
    tool_name = "google_places"
    
    # Check if we should skip directly to fallback
    if tool_health.should_use_fallback(tool_name):
        logger.warning(f"Skipping {tool_name} due to repeated failures, using fallback")
        result = await generate_attractions_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            interests=intent.interests,
            duration_days=intent.duration_days,
            currency=intent.budget_currency,
        )
        return {
            "data": result.data[:20],
            "is_estimated": True,
            "error_message": "Service temporarily unavailable",
        }
    
    try:
        tool = GoogleMapsTransitTool.place_search

        # Search for different types based on interests
        all_attractions = []

        queries = [
            f"top attractions in {intent.destination_city}",
            f"popular restaurants in {intent.destination_city}",
        ]

        # Add interest-specific searches
        for interest in intent.interests[:3]:
            queries.append(f"{interest} activities in {intent.destination_city}")

        for query in queries:
            try:
                result = await tool._arun(query=query, radius=10000)
                if result:
                    all_attractions.extend(result[:5])
            except Exception as query_error:
                logger.warning(f"Query '{query}' failed: {query_error}")
                continue

        if all_attractions:
            tool_health.record_success(tool_name)
            return {
                "data": all_attractions[:20],
                "is_estimated": False,
            }
        else:
            # All queries failed, use fallback
            raise Exception("All attraction queries failed")
            
    except Exception as e:
        logger.warning(f"Attractions search failed: {e}, using fallback")
        tool_health.record_failure(tool_name, e)
        
        # Generate fallback data
        result = await generate_attractions_fallback(
            city=intent.destination_city,
            country=intent.destination_country,
            interests=intent.interests,
            duration_days=intent.duration_days,
            currency=intent.budget_currency,
            error=e,
        )
        return {
            "data": result.data[:20] if result.data else [],
            "is_estimated": True,
            "error_message": str(e),
            "error_type": classify_error(e),
        }


# Keep old functions for backward compatibility but mark as deprecated
async def _search_flights(intent: ExtractedIntent) -> list[dict]:
    """Search for flights using Amadeus. DEPRECATED: Use _search_flights_with_fallback."""
    result = await _search_flights_with_fallback(intent)
    return result.get("data", [])


async def _search_hotels(intent: ExtractedIntent) -> list[dict]:
    """Search for hotels using Amadeus. DEPRECATED: Use _search_hotels_with_fallback."""
    result = await _search_hotels_with_fallback(intent)
    return result.get("data", [])


async def _get_weather(intent: ExtractedIntent) -> dict | None:
    """Get weather forecast. DEPRECATED: Use _get_weather_with_fallback."""
    result = await _get_weather_with_fallback(intent)
    return result.get("data")


async def _search_attractions(intent: ExtractedIntent) -> list[dict]:
    """Search for attractions using Google Maps. DEPRECATED: Use _search_attractions_with_fallback."""
    result = await _search_attractions_with_fallback(intent)
    return result.get("data", [])


def _get_airport_code(city: str) -> str:
    """Get IATA airport code for a city."""
    # Common airport codes - expand as needed
    codes = {
        "tokyo": "NRT",
        "osaka": "KIX",
        "bangkok": "BKK",
        "singapore": "SIN",
        "hong kong": "HKG",
        "seoul": "ICN",
        "taipei": "TPE",
        "kuala lumpur": "KUL",
        "bali": "DPS",
        "phuket": "HKT",
        "paris": "CDG",
        "london": "LHR",
        "new york": "JFK",
        "los angeles": "LAX",
    }
    return codes.get(city.lower(), city[:3].upper())


def _get_city_code(city: str) -> str:
    """Get IATA city code."""
    codes = {
        "tokyo": "TYO",
        "osaka": "OSA",
        "bangkok": "BKK",
        "singapore": "SIN",
        "hong kong": "HKG",
        "seoul": "SEL",
        "taipei": "TPE",
        "kuala lumpur": "KUL",
        "bali": "DPS",
        "phuket": "HKT",
        "paris": "PAR",
        "london": "LON",
        "new york": "NYC",
        "los angeles": "LAX",
    }
    return codes.get(city.lower(), city[:3].upper())


async def itinerary_generation_node(state: AgentState) -> dict:
    """
    Generate the actual itinerary using LLM with gathered data.
    
    Creates day-by-day plans with activities, timing, and details.
    """
    intent = state["intent"]
    gathered = state["gathered_data"]

    if not intent:
        return {"error": "No intent available", "current_step": PlannerStep.ERROR}

    logger.info(f"Generating itinerary for {intent.destination_city}")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.ITINERARY_GENERATION,
            progress=60,
            message="🧠 AI is crafting your perfect itinerary...",
        )

    llm = get_llm(temperature=0.8)

    # Prepare weather summary
    weather_summary = "Weather data not available"
    if gathered and gathered.weather_forecast:
        forecasts = gathered.weather_forecast.get("daily_forecasts", [])
        if forecasts:
            weather_lines = []
            for f in forecasts[:7]:
                # Handle both nested and flat condition formats
                condition = f.get('condition', 'Unknown')
                if isinstance(condition, dict):
                    condition = condition.get('main', 'Unknown')
                # Handle both temp_min/temp_max and temp_low/temp_high formats
                temp_min = f.get('temp_min') or f.get('temp_low', 'N/A')
                temp_max = f.get('temp_max') or f.get('temp_high', 'N/A')
                weather_lines.append(f"- {f.get('date', 'N/A')}: {condition}, {temp_min}-{temp_max}°C")
            weather_summary = "\n".join(weather_lines)

    # Prepare attractions
    attractions_text = "No specific attractions found"
    if gathered and gathered.attractions:
        attractions_text = "\n".join(
            f"- {a.get('name', 'Unknown')}: {a.get('formatted_address', 'N/A')} (Rating: {a.get('rating', 'N/A')})"
            for a in gathered.attractions[:15]
        )

    # Prepare flights and hotels
    flights_text = "No flights searched"
    if gathered and gathered.flights:
        flights_text = "\n".join(
            f"- {f.get('carrier', 'Unknown')}: {f.get('total_price', 'N/A')} {intent.budget_currency}"
            for f in gathered.flights[:3]
        )

    hotels_text = "Search for hotels on arrival"
    if gathered and gathered.hotels:
        hotels_text = "\n".join(
            f"- {h.get('name', 'Unknown')}: {h.get('price_per_night', 'N/A')}/night"
            for h in gathered.hotels[:5]
        )

    prompt = ChatPromptTemplate.from_template(ITINERARY_GENERATION_PROMPT)

    messages = prompt.format_messages(
        destination_city=intent.destination_city,
        destination_country=intent.destination_country,
        start_date=intent.start_date.isoformat(),
        end_date=intent.end_date.isoformat(),
        duration_days=intent.duration_days,
        budget_amount=str(intent.budget_amount),
        budget_currency=intent.budget_currency,
        travelers_count=intent.travelers_count,
        trip_type=intent.trip_type or "leisure",
        interests=", ".join(intent.interests) if intent.interests else "general sightseeing",
        pace_preference=intent.pace_preference,
        weather_summary=weather_summary,
        attractions=attractions_text,
        flights=flights_text,
        hotels=hotels_text,
    )

    try:
        response = await llm.ainvoke(messages)

        # Parse response and create daily plans
        daily_plans = await _parse_and_enhance_daily_plans(
            response.content,
            intent,
            gathered,
        )

        return {
            "daily_plans": daily_plans,
            "current_step": PlannerStep.ROUTE_OPTIMIZATION,
            "step_progress": 75,
            "step_message": "Optimizing travel routes between activities...",
        }

    except Exception as e:
        logger.error(f"Itinerary generation failed: {e}")
        # Fall back to generated itinerary
        daily_plans = _generate_fallback_daily_plans(intent, gathered)
        return {
            "daily_plans": daily_plans,
            "current_step": PlannerStep.ROUTE_OPTIMIZATION,
            "step_progress": 75,
            "step_message": "Using optimized template for your trip...",
        }


async def _parse_and_enhance_daily_plans(
    llm_response: str,
    intent: ExtractedIntent,
    gathered: GatheredData | None,
) -> list[AIDailyPlan]:
    """Parse LLM response and enhance with additional details."""
    import json

    daily_plans = []

    try:
        # Clean and parse JSON
        content = llm_response.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        raw_plans = json.loads(content)

        for i, raw_plan in enumerate(raw_plans):
            day_number = i + 1
            plan_date = intent.start_date + timedelta(days=i)

            activities = []
            for raw_activity in raw_plan.get("activities", []):
                activity = await _create_ai_activity(
                    raw_activity,
                    intent.destination_city,
                    gathered,
                )
                activities.append(activity)

            # Add transit details between activities
            activities = await _add_transit_details(activities, intent.destination_city)

            # Get weather for this day
            weather_context = _get_weather_for_date(gathered, plan_date)

            daily_plan = AIDailyPlan(
                day_number=day_number,
                date=plan_date,
                title=raw_plan.get("title", f"Day {day_number}"),
                summary=raw_plan.get("summary"),
                activities=activities,
                total_cost=sum(a.estimated_cost for a in activities),
                total_walking_minutes=sum(
                    (t.transit_to_next.duration_minutes if t.transit_to_next and t.transit_to_next.mode == TransitMode.WALK else 0)
                    for t in activities
                ),
                total_transit_minutes=sum(
                    (t.transit_to_next.duration_minutes if t.transit_to_next and t.transit_to_next.mode != TransitMode.WALK else 0)
                    for t in activities
                ),
                weather_summary=weather_context,
                notes=raw_plan.get("notes"),
            )
            daily_plans.append(daily_plan)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        daily_plans = _generate_fallback_daily_plans(intent, gathered)

    return daily_plans


async def _create_ai_activity(
    raw_activity: dict,
    city: str,
    gathered: GatheredData | None,
) -> AIActivity:
    """Create AIActivity from raw LLM output."""
    # Parse time
    time_str = raw_activity.get("time", "10:00")
    try:
        start_time = time.fromisoformat(time_str)
    except ValueError:
        start_time = time(10, 0)

    duration = raw_activity.get("duration", 60)
    end_time = (
        datetime.combine(date.today(), start_time) + timedelta(minutes=duration)
    ).time()

    # Get location info (simplified - would use Google Places in production)
    location = LocationInfo(
        name=raw_activity.get("location", raw_activity.get("title", "Unknown")),
        address=raw_activity.get("address"),
        latitude=raw_activity.get("lat", 0.0),
        longitude=raw_activity.get("lng", 0.0),
        google_place_id=raw_activity.get("place_id"),
    )

    # Map category
    category_map = {
        "sightseeing": "sightseeing",
        "culture": "sightseeing",
        "food": "dining",
        "dining": "dining",
        "restaurant": "dining",
        "shopping": "shopping",
        "entertainment": "entertainment",
        "nightlife": "entertainment",
        "transportation": "transportation",
        "accommodation": "accommodation",
        "nature": "sightseeing",
    }
    from app.domains.itinerary.models import ActivityCategory
    category_str = raw_activity.get("category", "sightseeing").lower()
    category = ActivityCategory(category_map.get(category_str, "other"))

    return AIActivity(
        title=raw_activity.get("title", "Activity"),
        description=raw_activity.get("description", ""),
        category=category,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration,
        location=location,
        estimated_cost=Decimal(str(raw_activity.get("cost", 0))),
        cost_currency=raw_activity.get("currency", "THB"),
        local_tips=raw_activity.get("tips", []),
        best_for=raw_activity.get("best_for", []),
        requires_booking=raw_activity.get("requires_booking", False),
        tags=raw_activity.get("tags", []),
    )


async def _add_transit_details(
    activities: list[AIActivity],
    city: str,
) -> list[AIActivity]:
    """Add transit details between consecutive activities."""
    if len(activities) <= 1:
        return activities

    enhanced = []
    tool = GoogleMapsTransitTool.directions

    for i, activity in enumerate(activities):
        if i < len(activities) - 1:
            next_activity = activities[i + 1]

            try:
                # Get transit directions
                origin = f"{activity.location.latitude},{activity.location.longitude}"
                destination = f"{next_activity.location.latitude},{next_activity.location.longitude}"

                if activity.location.latitude != 0 and next_activity.location.latitude != 0:
                    result = await tool._arun(
                        origin=activity.location.name,
                        destination=next_activity.location.name,
                        mode="transit",
                    )

                    if result and result.get("legs"):
                        leg = result["legs"][0]
                        steps = leg.get("steps", [])

                        # Find transit step with details
                        transit_detail = None
                        for step in steps:
                            if step.get("transit_details"):
                                td = step["transit_details"]
                                exit_info = step.get("exit_info")

                                transit_detail = TransitDetail(
                                    mode=TransitMode.SUBWAY if td.get("vehicle_type") == "SUBWAY" else TransitMode.BUS,
                                    duration_minutes=leg.get("duration_seconds", 0) // 60,
                                    distance_meters=leg.get("distance_meters"),
                                    line_name=td.get("line_name"),
                                    line_color=td.get("line_color"),
                                    station_name=td.get("departure_stop", {}).get("name"),
                                    destination_station=td.get("arrival_stop", {}).get("name"),
                                    exit_number=exit_info.get("exit_number") if exit_info else None,
                                    instructions=step.get("instruction"),
                                )
                                break

                        # Default to walking if no transit found
                        if not transit_detail:
                            transit_detail = TransitDetail(
                                mode=TransitMode.WALK,
                                duration_minutes=leg.get("duration_seconds", 600) // 60,
                                distance_meters=leg.get("distance_meters"),
                            )

                        activity.transit_to_next = transit_detail

            except Exception as e:
                logger.warning(f"Failed to get transit for {activity.title}: {e}")
                # Default walking estimate
                activity.transit_to_next = TransitDetail(
                    mode=TransitMode.WALK,
                    duration_minutes=15,
                )

        enhanced.append(activity)

    return enhanced


def _get_weather_for_date(
    gathered: GatheredData | None,
    target_date: date,
) -> WeatherContext | None:
    """Get weather context for a specific date."""
    if not gathered or not gathered.weather_forecast:
        return None

    forecasts = gathered.weather_forecast.get("daily_forecasts", [])
    for forecast in forecasts:
        if forecast.get("date") == target_date.isoformat():
            condition_map = {
                "clear": WeatherConditionEnum.SUNNY,
                "sunny": WeatherConditionEnum.SUNNY,
                "clouds": WeatherConditionEnum.CLOUDY,
                "cloudy": WeatherConditionEnum.CLOUDY,
                "rain": WeatherConditionEnum.RAINY,
                "drizzle": WeatherConditionEnum.RAINY,
                "snow": WeatherConditionEnum.SNOWY,
                "thunderstorm": WeatherConditionEnum.STORMY,
            }

            # Handle both nested and flat condition formats
            condition_raw = forecast.get("condition", "sunny")
            if isinstance(condition_raw, dict):
                condition_str = condition_raw.get("main", "sunny").lower()
            else:
                condition_str = str(condition_raw).lower()
            condition = condition_map.get(condition_str, WeatherConditionEnum.SUNNY)

            temp_c = forecast.get("temp_day") or forecast.get("temp_high", 25)

            # Handle both nested and flat icon formats
            icon_raw = forecast.get("condition", {})
            icon = icon_raw.get("icon") if isinstance(icon_raw, dict) else None

            return WeatherContext(
                condition=condition,
                temperature_celsius=temp_c,
                temperature_fahrenheit=temp_c * 9 / 5 + 32,
                humidity_percent=forecast.get("humidity") or forecast.get("humidity_percent"),
                precipitation_chance=int(forecast.get("precipitation_probability", forecast.get("precipitation_chance", 0)) * 100 if forecast.get("precipitation_probability") else forecast.get("precipitation_chance", 0)),
                uv_index=forecast.get("uv_index"),
                advisory=forecast.get("advisory"),
                icon=icon,
            )

    return None


def _generate_fallback_daily_plans(
    intent: ExtractedIntent,
    gathered: GatheredData | None,
) -> list[AIDailyPlan]:
    """Generate fallback daily plans when LLM fails."""
    daily_plans = []

    for day in range(intent.duration_days):
        day_number = day + 1
        plan_date = intent.start_date + timedelta(days=day)

        # Create basic activities for the day
        activities = [
            AIActivity(
                title=f"Morning exploration in {intent.destination_city}",
                description=f"Start your day exploring {intent.destination_city}",
                category="SIGHTSEEING",
                start_time=time(9, 0),
                end_time=time(12, 0),
                duration_minutes=180,
                location=LocationInfo(
                    name=f"City Center, {intent.destination_city}",
                    latitude=0.0,
                    longitude=0.0,
                ),
                estimated_cost=Decimal("0"),
            ),
            AIActivity(
                title="Lunch at local restaurant",
                description="Enjoy local cuisine",
                category="DINING",
                start_time=time(12, 30),
                end_time=time(14, 0),
                duration_minutes=90,
                location=LocationInfo(
                    name=f"Local Restaurant, {intent.destination_city}",
                    latitude=0.0,
                    longitude=0.0,
                ),
                estimated_cost=Decimal("500"),
            ),
            AIActivity(
                title=f"Afternoon activity - Day {day_number}",
                description=f"Continue exploring {intent.destination_city}",
                category="SIGHTSEEING",
                start_time=time(14, 30),
                end_time=time(18, 0),
                duration_minutes=210,
                location=LocationInfo(
                    name=f"Attraction, {intent.destination_city}",
                    latitude=0.0,
                    longitude=0.0,
                ),
                estimated_cost=Decimal("300"),
            ),
        ]

        daily_plan = AIDailyPlan(
            day_number=day_number,
            date=plan_date,
            title=f"Day {day_number} in {intent.destination_city}",
            summary=f"Exploring {intent.destination_city}",
            activities=activities,
            total_cost=sum(a.estimated_cost for a in activities),
            total_walking_minutes=30,
            total_transit_minutes=20,
            weather_summary=_get_weather_for_date(gathered, plan_date),
        )
        daily_plans.append(daily_plan)

    return daily_plans


async def route_optimization_node(state: AgentState) -> dict:
    """
    Optimize routes between activities using Google Maps.
    
    Adds detailed transit information and polylines.
    """
    logger.info("Optimizing routes")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.ROUTE_OPTIMIZATION,
            progress=85,
            message="🗺️ Optimizing travel routes...",
        )

    # Routes are already added in itinerary_generation
    # This node can add additional optimization if needed

    return {
        "current_step": PlannerStep.MONETIZATION,
        "step_progress": 90,
        "step_message": "Adding booking options...",
    }


async def monetization_node(state: AgentState) -> dict:
    """
    Add affiliate booking links from Travelpayouts.
    
    Injects monetization opportunities into the itinerary.
    """
    intent = state["intent"]
    gathered = state["gathered_data"]
    daily_plans = state.get("daily_plans", [])

    if not intent:
        return {"current_step": PlannerStep.FINALIZATION}

    logger.info("Adding monetization links")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.MONETIZATION,
            progress=92,
            message="💰 Finding best booking deals...",
        )

    booking_options = []

    try:
        # Generate flight affiliate links
        if intent.origin_city:
            flight_tool = TravelpayoutsTool.flight_link
            flight_link = await flight_tool._arun(
                origin=_get_airport_code(intent.origin_city),
                destination=_get_airport_code(intent.destination_city),
                departure_date=intent.start_date.isoformat(),
                return_date=intent.end_date.isoformat(),
                adults=intent.travelers_count,
                currency=intent.budget_currency,
            )

            # Create booking option from gathered flight data or generic
            if gathered and gathered.flights:
                for flight in gathered.flights[:3]:
                    booking_options.append(
                        BookingOption(
                            booking_type=BookingType.FLIGHT,
                            provider=flight.get("carrier", "Multiple Airlines"),
                            price=Decimal(str(flight.get("total_price", 0))),
                            currency=intent.budget_currency,
                            title=f"Flights to {intent.destination_city}",
                            departure_time=datetime.fromisoformat(flight["segments"][0]["departure_time"]) if flight.get("segments") else None,
                            arrival_time=datetime.fromisoformat(flight["segments"][-1]["arrival_time"]) if flight.get("segments") else None,
                            stops=flight.get("stops", 0),
                            affiliate_url=flight_link.get("affiliate_url", ""),
                        )
                    )
            else:
                booking_options.append(
                    BookingOption(
                        booking_type=BookingType.FLIGHT,
                        provider="Multiple Airlines",
                        price=Decimal("0"),
                        currency=intent.budget_currency,
                        title=f"Search flights to {intent.destination_city}",
                        affiliate_url=flight_link.get("affiliate_url", ""),
                    )
                )

        # Generate hotel affiliate links
        hotel_tool = TravelpayoutsTool.hotel_link
        hotel_link = await hotel_tool._arun(
            location=intent.destination_city,
            check_in_date=intent.start_date.isoformat(),
            check_out_date=intent.end_date.isoformat(),
            adults=intent.travelers_count,
            currency=intent.budget_currency,
        )

        if gathered and gathered.hotels:
            for hotel in gathered.hotels[:3]:
                booking_options.append(
                    BookingOption(
                        booking_type=BookingType.HOTEL,
                        provider=hotel.get("chain_code", "Hotel"),
                        price=Decimal(str(hotel.get("total_price", 0))),
                        price_per_night=Decimal(str(hotel.get("price_per_night", 0))),
                        currency=intent.budget_currency,
                        title=hotel.get("name", "Hotel"),
                        hotel_stars=hotel.get("star_rating"),
                        check_in_date=intent.start_date,
                        check_out_date=intent.end_date,
                        affiliate_url=hotel_link.get("affiliate_url", ""),
                    )
                )
        else:
            booking_options.append(
                BookingOption(
                    booking_type=BookingType.HOTEL,
                    provider="Multiple Hotels",
                    price=Decimal("0"),
                    currency=intent.budget_currency,
                    title=f"Search hotels in {intent.destination_city}",
                    check_in_date=intent.start_date,
                    check_out_date=intent.end_date,
                    affiliate_url=hotel_link.get("affiliate_url", ""),
                )
            )

    except Exception as e:
        logger.warning(f"Monetization failed: {e}")
        # Continue without affiliate links

    return {
        "booking_options": booking_options,
        "current_step": PlannerStep.FINALIZATION,
        "step_progress": 95,
        "step_message": "Finalizing your itinerary...",
    }


async def finalization_node(state: AgentState) -> dict:
    """
    Finalize the itinerary and create the complete output.
    """
    intent = state["intent"]
    daily_plans = state.get("daily_plans", [])
    booking_options = state.get("booking_options", [])
    gathered = state.get("gathered_data")

    if not intent:
        return {"error": "No intent available", "current_step": PlannerStep.ERROR}

    logger.info("Finalizing itinerary")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=PlannerStep.FINALIZATION,
            progress=98,
            message="✨ Putting the finishing touches...",
        )

    # Calculate total cost
    activities_cost = sum(
        plan.total_cost for plan in daily_plans
    )

    # Get weather summary
    weather_summary = None
    packing = None
    if gathered and gathered.weather_forecast:
        weather_summary = gathered.weather_forecast.get("period_summary")
        packing = gathered.weather_forecast.get("packing_suggestions")

    # Separate booking options by type
    flight_options = [b for b in booking_options if b.booking_type == BookingType.FLIGHT]
    hotel_options = [b for b in booking_options if b.booking_type == BookingType.HOTEL]
    activity_bookings = [b for b in booking_options if b.booking_type not in [BookingType.FLIGHT, BookingType.HOTEL]]

    final_itinerary = AIFullItinerary(
        title=f"{intent.duration_days}-Day {intent.destination_city} Adventure",
        destination=f"{intent.destination_city}, {intent.destination_country}",
        destination_country=intent.destination_country,
        destination_city=intent.destination_city,
        start_date=intent.start_date,
        end_date=intent.end_date,
        duration_days=intent.duration_days,
        traveler_count=intent.travelers_count,
        trip_type=intent.trip_type,
        daily_plans=daily_plans,
        flight_options=flight_options if flight_options else None,
        hotel_options=hotel_options if hotel_options else None,
        activity_bookings=activity_bookings if activity_bookings else None,
        total_estimated_cost=activities_cost + sum(
            b.price for b in booking_options if b.price
        ),
        cost_breakdown={
            "activities": activities_cost,
            "flights": sum(b.price for b in flight_options) if flight_options else Decimal("0"),
            "hotels": sum(b.price for b in hotel_options) if hotel_options else Decimal("0"),
        },
        currency=intent.budget_currency,
        weather_summary=weather_summary,
        packing_suggestions=packing,
        generated_at=datetime.now(timezone.utc),
        sources_used=["Amadeus", "Google Maps", "OpenWeatherMap", "Travelpayouts"],
    )

    return {
        "final_itinerary": final_itinerary,
        "current_step": PlannerStep.FINALIZATION,
        "step_progress": 100,
        "step_message": "🎉 Your itinerary is ready!",
    }


async def error_handling_node(state: AgentState) -> dict:
    """Handle errors and decide on retry or fail."""
    logger.error(f"Error in planning: {state.get('error')}")

    retry_count = state.get("retry_count", 0)

    if state.get("should_retry") and retry_count < 3:
        return {
            "current_step": PlannerStep.INTENT_EXTRACTION,
            "should_retry": False,
            "step_message": f"Retrying... (attempt {retry_count + 1}/3)",
        }

    return {
        "step_message": f"Failed: {state.get('error', 'Unknown error')}",
    }


# ============ Edge Conditions ============


def should_continue(state: AgentState) -> Literal["continue", "error", "end"]:
    """Determine next step based on current state."""
    if state.get("error"):
        return "error"

    if state["current_step"] == PlannerStep.FINALIZATION and state.get("final_itinerary"):
        return "end"

    return "continue"


def route_after_data_gathering(state: AgentState) -> Literal["generate", "retry_weather"]:
    """Check if we need to retry due to bad weather data."""
    gathered = state.get("gathered_data")

    if not gathered:
        return "generate"

    # Check if weather indicates we should suggest alternatives
    weather = gathered.weather_forecast
    if weather:
        forecasts = weather.get("daily_forecasts", [])
        rainy_days = sum(
            1 for f in forecasts
            if f.get("precipitation_probability", 0) > 0.7
        )

        # If more than half the days are rainy, we might want to adjust
        if rainy_days > len(forecasts) / 2:
            logger.info("High rain probability detected, will prioritize indoor activities")

    return "generate"


def get_next_node(state: AgentState) -> str:
    """Route to next node based on current step."""
    step = state["current_step"]

    routes = {
        PlannerStep.INTENT_EXTRACTION: "data_gathering",
        PlannerStep.DATA_GATHERING: "itinerary_generation",
        PlannerStep.ITINERARY_GENERATION: "route_optimization",
        PlannerStep.ROUTE_OPTIMIZATION: "monetization",
        PlannerStep.MONETIZATION: "finalization",
        PlannerStep.FINALIZATION: END,
        PlannerStep.ERROR: "error_handling",
    }

    return routes.get(step, END)


# ============ Graph Builder ============


def build_planner_graph() -> StateGraph:
    """
    Build the LangGraph workflow for itinerary planning.
    
    Flow:
    1. intent_extraction -> Parse user prompt
    2. data_gathering -> Fetch flights, hotels, weather (parallel)
    3. itinerary_generation -> Create daily plans with LLM
    4. route_optimization -> Add transit details
    5. monetization -> Inject affiliate links
    6. finalization -> Compile final itinerary
    
    Error handling at each step with retry capability.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intent_extraction", intent_extraction_node)
    workflow.add_node("data_gathering", data_gathering_node)
    workflow.add_node("itinerary_generation", itinerary_generation_node)
    workflow.add_node("route_optimization", route_optimization_node)
    workflow.add_node("monetization", monetization_node)
    workflow.add_node("finalization", finalization_node)
    workflow.add_node("error_handling", error_handling_node)

    # Set entry point
    workflow.set_entry_point("intent_extraction")

    # Add edges
    workflow.add_conditional_edges(
        "intent_extraction",
        should_continue,
        {
            "continue": "data_gathering",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "data_gathering",
        should_continue,
        {
            "continue": "itinerary_generation",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "itinerary_generation",
        should_continue,
        {
            "continue": "route_optimization",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "route_optimization",
        should_continue,
        {
            "continue": "monetization",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "monetization",
        should_continue,
        {
            "continue": "finalization",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "finalization",
        should_continue,
        {
            "continue": END,
            "error": "error_handling",
            "end": END,
        },
    )

    # Error handling can retry or end
    workflow.add_conditional_edges(
        "error_handling",
        lambda s: "retry" if s.get("should_retry") and s.get("retry_count", 0) < 3 else "end",
        {
            "retry": "intent_extraction",
            "end": END,
        },
    )

    return workflow


# Compile the graph
planner_graph = build_planner_graph().compile()


# ============ Public Interface ============


async def run_planner(
    itinerary_id: str,
    user_prompt: str,
    user_id: str | None = None,
    preferences: dict | None = None,
    progress_callback: Any | None = None,
) -> AIFullItinerary | None:
    """
    Run the planner workflow and return generated itinerary.
    
    Args:
        itinerary_id: Unique ID for this itinerary
        user_prompt: Natural language travel request
        user_id: Optional user ID for personalization
        preferences: Optional user preferences dict
        progress_callback: Optional async callback for progress updates
        
    Returns:
        AIFullItinerary or None if generation failed
    """
    initial_state: AgentState = {
        "user_prompt": user_prompt,
        "itinerary_id": itinerary_id,
        "user_id": user_id,
        "preferences": preferences,
        "messages": [],
        "current_step": PlannerStep.INTENT_EXTRACTION,
        "step_progress": 0,
        "step_message": "Starting...",
        "intent": None,
        "gathered_data": None,
        "daily_plans": [],
        "booking_options": [],
        "final_itinerary": None,
        "error": None,
        "retry_count": 0,
        "should_retry": False,
        "progress_callback": progress_callback,
    }

    try:
        # Run the graph
        final_state = await planner_graph.ainvoke(initial_state)

        if final_state.get("error"):
            logger.error(f"Planner failed: {final_state['error']}")
            return None

        return final_state.get("final_itinerary")

    except Exception as e:
        logger.error(f"Planner execution failed: {e}")
        return None
