"""LangChain Tools for the Intelligence Engine.

This module provides async tools for external API integrations:
- AmadeusTool: Real-time flights and hotels
- GoogleMapsTransitTool: Directions and transit information
- WeatherTool: Weather forecasts for destinations
- TravelpayoutsTool: Affiliate deep links for bookings
- Fallback: AI-powered fallback data when APIs fail
"""

from app.domains.itinerary.tools.amadeus import AmadeusTool
from app.domains.itinerary.tools.base import (
    APIClientError,
    AuthenticationError,
    RateLimitError,
    ToolError,
)
from app.domains.itinerary.tools.fallback import (
    FallbackResult,
    ToolErrorType,
    classify_error,
    generate_attractions_fallback,
    generate_flight_fallback,
    generate_hotel_fallback,
    generate_transit_fallback,
    generate_weather_fallback,
    tool_health,
)
from app.domains.itinerary.tools.google_maps import GoogleMapsTransitTool
from app.domains.itinerary.tools.travelpayouts import TravelpayoutsTool
from app.domains.itinerary.tools.weather import WeatherTool

__all__ = [
    # Main Tools
    "AmadeusTool",
    "GoogleMapsTransitTool",
    "TravelpayoutsTool",
    "WeatherTool",
    # Error Classes
    "ToolError",
    "APIClientError",
    "RateLimitError",
    "AuthenticationError",
    # Fallback System
    "FallbackResult",
    "ToolErrorType",
    "classify_error",
    "generate_flight_fallback",
    "generate_hotel_fallback",
    "generate_weather_fallback",
    "generate_attractions_fallback",
    "generate_transit_fallback",
    "tool_health",
]
