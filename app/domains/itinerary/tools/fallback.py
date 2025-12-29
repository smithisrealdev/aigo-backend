"""
AiGo Backend - Fallback Data Provider
Provides AI-generated estimated data when external APIs fail.

When Amadeus, Google Maps, or Weather APIs are unavailable,
this module generates reasonable estimates based on AI knowledge
with is_estimated: true flags.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============ Error Classification ============


class ToolErrorType:
    """Classification of tool errors for fallback handling."""
    
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    SERVICE_UNAVAILABLE = "service_unavailable"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> str:
    """Classify an exception into a ToolErrorType."""
    error_msg = str(error).lower()
    error_type = type(error).__name__.lower()
    
    if "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
        return ToolErrorType.RATE_LIMIT
    elif "timeout" in error_msg or "timed out" in error_msg:
        return ToolErrorType.TIMEOUT
    elif "401" in error_msg or "403" in error_msg or "auth" in error_msg:
        return ToolErrorType.AUTHENTICATION
    elif "503" in error_msg or "502" in error_msg or "unavailable" in error_msg:
        return ToolErrorType.SERVICE_UNAVAILABLE
    elif "connection" in error_msg or "network" in error_msg:
        return ToolErrorType.NETWORK_ERROR
    elif "json" in error_msg or "parse" in error_msg:
        return ToolErrorType.INVALID_RESPONSE
    else:
        return ToolErrorType.UNKNOWN


# ============ Fallback Result Wrapper ============


class FallbackResult:
    """Wrapper for fallback/estimated results."""
    
    def __init__(
        self,
        data: Any,
        is_estimated: bool = False,
        source: str = "live_api",
        error_type: str | None = None,
        error_message: str | None = None,
        confidence: float = 1.0,
    ):
        self.data = data
        self.is_estimated = is_estimated
        self.source = source  # "live_api", "ai_fallback", "cache", "static"
        self.error_type = error_type
        self.error_message = error_message
        self.confidence = confidence  # 0.0-1.0, how confident we are in this data
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "is_estimated": self.is_estimated,
            "source": self.source,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "confidence": self.confidence,
        }
    
    @property
    def has_data(self) -> bool:
        """Check if result has usable data."""
        if self.data is None:
            return False
        if isinstance(self.data, (list, dict)):
            return len(self.data) > 0
        return True


# ============ LLM Configuration ============


def get_fallback_llm(temperature: float = 0.5) -> ChatOpenAI:
    """Get ChatOpenAI configured for fallback generation."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Fallback Prompts ============


FLIGHT_FALLBACK_PROMPT = """You are a travel expert providing flight estimates when real-time data is unavailable.

Route: {origin} to {destination}
Dates: {departure_date} to {return_date}
Passengers: {adults} adults
Cabin: {cabin_class}

Based on your knowledge of typical flight prices and durations for this route:

1. Estimate 3 realistic flight options from different airlines
2. Consider the route distance, typical carriers, and seasonal pricing
3. Include both direct and connecting flight options if applicable

Provide JSON array with each flight having:
- carrier: Airline name
- carrier_code: 2-letter IATA code
- departure_airport: origin code
- arrival_airport: destination code  
- departure_time: estimated departure (HH:MM)
- arrival_time: estimated arrival (HH:MM)
- duration_hours: flight duration
- stops: number of stops (0 for direct)
- total_price: estimated price in {currency}
- price_currency: {currency}
- is_estimated: true (ALWAYS set this to true)
- booking_class: economy, premium_economy, business, first

Return ONLY valid JSON array, no markdown."""


HOTEL_FALLBACK_PROMPT = """You are a travel expert providing hotel estimates when real-time data is unavailable.

Destination: {city}, {country}
Dates: {check_in} to {check_out} ({nights} nights)
Guests: {adults} adults, {rooms} room(s)
Budget Level: {budget_level}

Based on your knowledge of hotels in this destination:

1. Suggest 5 realistic hotel options across different price points
2. Include well-known international chains and popular local hotels
3. Consider the city's typical hotel pricing

Provide JSON array with each hotel having:
- name: Hotel name
- star_rating: 1-5 stars
- area: District/neighborhood name
- address: Approximate address
- price_per_night: estimated price in {currency}
- total_price: total for all nights in {currency}
- currency: {currency}
- amenities: array of common amenities
- is_estimated: true (ALWAYS set this to true)
- confidence: 0.6-0.8 based on how confident you are

Return ONLY valid JSON array, no markdown."""


WEATHER_FALLBACK_PROMPT = """You are a meteorology expert providing weather estimates when forecast APIs are unavailable.

Location: {city}, {country}
Dates: {start_date} to {end_date}

Based on your knowledge of typical weather patterns for this location and time of year:

1. Provide daily weather forecasts
2. Consider seasonal patterns, monsoon seasons, typical temperatures
3. Be conservative with predictions

Provide JSON with:
- location: city name
- country: country name
- daily_forecasts: array of daily forecasts, each with:
  - date: YYYY-MM-DD
  - day_name: day of week
  - temp_high: typical high temperature (Celsius)
  - temp_low: typical low temperature (Celsius)
  - condition: main condition (Clear, Clouds, Rain, Snow, etc.)
  - description: brief description
  - humidity_percent: typical humidity
  - precipitation_chance: percentage
  - wind_speed_kmh: typical wind speed
  - is_estimated: true
- seasonal_notes: any important seasonal information
- packing_suggestions: array of items to pack

Return ONLY valid JSON, no markdown."""


ATTRACTIONS_FALLBACK_PROMPT = """You are a travel expert providing attraction recommendations when Places APIs are unavailable.

Destination: {city}, {country}
Interests: {interests}
Trip Duration: {duration_days} days

Based on your knowledge of this destination:

1. List 15-20 top attractions and points of interest
2. Include famous landmarks, museums, markets, parks
3. Consider the traveler's interests
4. Include a mix of free and paid attractions

Provide JSON array with each attraction having:
- name: Attraction name
- category: sightseeing, dining, shopping, entertainment, nature, culture
- description: 1-2 sentence description
- typical_duration_minutes: recommended time to spend
- estimated_cost: typical entry fee or cost (0 if free)
- currency: {currency}
- area: District/neighborhood
- best_time: best time to visit
- rating: estimated rating 1-5 (based on popularity)
- is_estimated: true (ALWAYS set this to true)
- tags: array of relevant tags

Return ONLY valid JSON array, no markdown."""


# ============ Fallback Generator Functions ============


async def generate_flight_fallback(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    adults: int = 1,
    cabin_class: str = "ECONOMY",
    currency: str = "THB",
    error: Exception | None = None,
) -> FallbackResult:
    """Generate estimated flight data using AI."""
    logger.info(f"Generating flight fallback for {origin} -> {destination}")
    
    try:
        llm = get_fallback_llm(temperature=0.4)
        prompt = ChatPromptTemplate.from_template(FLIGHT_FALLBACK_PROMPT)
        
        messages = prompt.format_messages(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date or "One-way",
            adults=adults,
            cabin_class=cabin_class,
            currency=currency,
        )
        
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        flights = json.loads(content)
        
        # Ensure all items have is_estimated flag
        for flight in flights:
            flight["is_estimated"] = True
        
        return FallbackResult(
            data={"offers": flights},
            is_estimated=True,
            source="ai_fallback",
            error_type=classify_error(error) if error else None,
            error_message=str(error) if error else None,
            confidence=0.6,
        )
        
    except Exception as e:
        logger.error(f"Flight fallback generation failed: {e}")
        return FallbackResult(
            data={"offers": []},
            is_estimated=True,
            source="ai_fallback",
            error_type=ToolErrorType.UNKNOWN,
            error_message=f"Fallback failed: {str(e)}",
            confidence=0.0,
        )


async def generate_hotel_fallback(
    city: str,
    country: str = "",
    check_in_date: str = "",
    check_out_date: str = "",
    adults: int = 1,
    rooms: int = 1,
    budget_level: str = "mid-range",
    currency: str = "THB",
    error: Exception | None = None,
) -> FallbackResult:
    """Generate estimated hotel data using AI."""
    logger.info(f"Generating hotel fallback for {city}")
    
    try:
        # Calculate nights
        from datetime import datetime
        nights = 1
        if check_in_date and check_out_date:
            try:
                d1 = datetime.fromisoformat(check_in_date)
                d2 = datetime.fromisoformat(check_out_date)
                nights = (d2 - d1).days
            except ValueError:
                nights = 3
        
        llm = get_fallback_llm(temperature=0.5)
        prompt = ChatPromptTemplate.from_template(HOTEL_FALLBACK_PROMPT)
        
        messages = prompt.format_messages(
            city=city,
            country=country or "Unknown",
            check_in=check_in_date,
            check_out=check_out_date,
            nights=nights,
            adults=adults,
            rooms=rooms,
            budget_level=budget_level,
            currency=currency,
        )
        
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        hotels = json.loads(content)
        
        # Ensure all items have is_estimated flag
        for hotel in hotels:
            hotel["is_estimated"] = True
        
        return FallbackResult(
            data={"offers": hotels},
            is_estimated=True,
            source="ai_fallback",
            error_type=classify_error(error) if error else None,
            error_message=str(error) if error else None,
            confidence=0.65,
        )
        
    except Exception as e:
        logger.error(f"Hotel fallback generation failed: {e}")
        return FallbackResult(
            data={"offers": []},
            is_estimated=True,
            source="ai_fallback",
            error_type=ToolErrorType.UNKNOWN,
            error_message=f"Fallback failed: {str(e)}",
            confidence=0.0,
        )


async def generate_weather_fallback(
    city: str,
    country: str = "",
    start_date: str = "",
    end_date: str = "",
    error: Exception | None = None,
) -> FallbackResult:
    """Generate estimated weather data using AI."""
    logger.info(f"Generating weather fallback for {city}")
    
    try:
        llm = get_fallback_llm(temperature=0.3)  # Lower temp for weather
        prompt = ChatPromptTemplate.from_template(WEATHER_FALLBACK_PROMPT)
        
        messages = prompt.format_messages(
            city=city,
            country=country or "Unknown",
            start_date=start_date,
            end_date=end_date,
        )
        
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        weather_data = json.loads(content)
        weather_data["is_estimated"] = True
        
        # Add is_estimated to each forecast
        if "daily_forecasts" in weather_data:
            for forecast in weather_data["daily_forecasts"]:
                forecast["is_estimated"] = True
        
        return FallbackResult(
            data=weather_data,
            is_estimated=True,
            source="ai_fallback",
            error_type=classify_error(error) if error else None,
            error_message=str(error) if error else None,
            confidence=0.5,  # Weather estimates are less reliable
        )
        
    except Exception as e:
        logger.error(f"Weather fallback generation failed: {e}")
        return FallbackResult(
            data=None,
            is_estimated=True,
            source="ai_fallback",
            error_type=ToolErrorType.UNKNOWN,
            error_message=f"Fallback failed: {str(e)}",
            confidence=0.0,
        )


async def generate_attractions_fallback(
    city: str,
    country: str = "",
    interests: list[str] | None = None,
    duration_days: int = 3,
    currency: str = "THB",
    error: Exception | None = None,
) -> FallbackResult:
    """Generate estimated attractions data using AI."""
    logger.info(f"Generating attractions fallback for {city}")
    
    try:
        llm = get_fallback_llm(temperature=0.6)
        prompt = ChatPromptTemplate.from_template(ATTRACTIONS_FALLBACK_PROMPT)
        
        messages = prompt.format_messages(
            city=city,
            country=country or "Unknown",
            interests=", ".join(interests) if interests else "general sightseeing, culture, food",
            duration_days=duration_days,
            currency=currency,
        )
        
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        attractions = json.loads(content)
        
        # Ensure all items have is_estimated flag
        for attraction in attractions:
            attraction["is_estimated"] = True
        
        return FallbackResult(
            data=attractions,
            is_estimated=True,
            source="ai_fallback",
            error_type=classify_error(error) if error else None,
            error_message=str(error) if error else None,
            confidence=0.7,
        )
        
    except Exception as e:
        logger.error(f"Attractions fallback generation failed: {e}")
        return FallbackResult(
            data=[],
            is_estimated=True,
            source="ai_fallback",
            error_type=ToolErrorType.UNKNOWN,
            error_message=f"Fallback failed: {str(e)}",
            confidence=0.0,
        )


async def generate_transit_fallback(
    origin: str,
    destination: str,
    city: str,
    mode: str = "transit",
    error: Exception | None = None,
) -> FallbackResult:
    """Generate estimated transit directions using AI."""
    logger.info(f"Generating transit fallback from {origin} to {destination}")
    
    try:
        llm = get_fallback_llm(temperature=0.4)
        
        prompt_template = """You are a local transit expert for {city}.

Generate realistic transit directions from "{origin}" to "{destination}".

Consider:
1. Most common transit options (subway, bus, walking)
2. Typical duration and distance
3. Major stations/stops along the way

Provide JSON with:
- duration_minutes: estimated total time
- distance_meters: estimated distance
- mode: primary mode (transit, walking, driving)
- summary: brief description of route
- steps: array of steps, each with:
  - instruction: what to do
  - mode: walking, subway, bus, train
  - duration_minutes: time for this step
  - line_name: transit line name (if applicable)
- is_estimated: true

Return ONLY valid JSON, no markdown."""

        messages = ChatPromptTemplate.from_template(prompt_template).format_messages(
            city=city,
            origin=origin,
            destination=destination,
        )
        
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        transit_data = json.loads(content)
        transit_data["is_estimated"] = True
        
        return FallbackResult(
            data=transit_data,
            is_estimated=True,
            source="ai_fallback",
            error_type=classify_error(error) if error else None,
            error_message=str(error) if error else None,
            confidence=0.55,
        )
        
    except Exception as e:
        logger.error(f"Transit fallback generation failed: {e}")
        return FallbackResult(
            data={
                "duration_minutes": 30,
                "distance_meters": 5000,
                "mode": "transit",
                "summary": "Transit directions unavailable",
                "is_estimated": True,
            },
            is_estimated=True,
            source="ai_fallback",
            error_type=ToolErrorType.UNKNOWN,
            error_message=f"Fallback failed: {str(e)}",
            confidence=0.2,
        )


# ============ Static Fallback Data ============


def get_static_airport_codes() -> dict[str, str]:
    """Return static airport code mappings as fallback."""
    return {
        "tokyo": "NRT",
        "osaka": "KIX",
        "kyoto": "KIX",
        "bangkok": "BKK",
        "singapore": "SIN",
        "hong kong": "HKG",
        "seoul": "ICN",
        "taipei": "TPE",
        "kuala lumpur": "KUL",
        "bali": "DPS",
        "jakarta": "CGK",
        "phuket": "HKT",
        "chiang mai": "CNX",
        "paris": "CDG",
        "london": "LHR",
        "new york": "JFK",
        "los angeles": "LAX",
        "san francisco": "SFO",
        "dubai": "DXB",
        "sydney": "SYD",
        "melbourne": "MEL",
    }


def get_static_city_codes() -> dict[str, str]:
    """Return static city code mappings as fallback."""
    return {
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


# ============ Error Status Tracking ============


class ToolHealthStatus:
    """Track health status of external tools."""
    
    def __init__(self):
        self._status: dict[str, dict] = {}
    
    def record_success(self, tool_name: str) -> None:
        """Record successful tool call."""
        if tool_name not in self._status:
            self._status[tool_name] = {"failures": 0, "successes": 0, "last_error": None}
        self._status[tool_name]["successes"] += 1
        self._status[tool_name]["failures"] = 0  # Reset consecutive failures
    
    def record_failure(self, tool_name: str, error: Exception) -> None:
        """Record failed tool call."""
        if tool_name not in self._status:
            self._status[tool_name] = {"failures": 0, "successes": 0, "last_error": None}
        self._status[tool_name]["failures"] += 1
        self._status[tool_name]["last_error"] = {
            "type": classify_error(error),
            "message": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat() if 'datetime' in dir() else None,
        }
    
    def should_use_fallback(self, tool_name: str, threshold: int = 3) -> bool:
        """Check if we should use fallback based on consecutive failures."""
        if tool_name not in self._status:
            return False
        return self._status[tool_name]["failures"] >= threshold
    
    def get_status(self, tool_name: str) -> dict:
        """Get current status for a tool."""
        return self._status.get(tool_name, {"failures": 0, "successes": 0, "last_error": None})


# Global health tracker
from datetime import timezone
tool_health = ToolHealthStatus()
