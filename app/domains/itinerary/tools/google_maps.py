"""Google Maps Transit Tool for fetching directions and exit information.

This tool integrates with Google Maps Routes/Directions API to provide:
- Transit directions between locations
- Walking directions
- Detailed transit information including exit numbers
- Polyline for map rendering
"""

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domains.itinerary.tools.base import APIClientError, BaseAsyncAPIClient

logger = logging.getLogger(__name__)


# ============ Input Schemas ============


class DirectionsInput(BaseModel):
    """Input schema for directions search."""

    origin: str = Field(
        ...,
        description="Origin location (address, place name, or 'lat,lng' coordinates)",
    )
    destination: str = Field(
        ...,
        description="Destination location (address, place name, or 'lat,lng' coordinates)",
    )
    mode: str = Field(
        default="transit",
        description="Travel mode: 'transit', 'walking', 'driving', 'bicycling'",
    )
    departure_time: str | None = Field(
        None,
        description="Departure time in ISO format or 'now'. Required for transit.",
    )
    arrival_time: str | None = Field(
        None,
        description="Desired arrival time in ISO format (alternative to departure_time)",
    )
    transit_mode: list[str] | None = Field(
        None,
        description="Preferred transit modes: ['bus', 'subway', 'train', 'tram', 'rail']",
    )
    language: str = Field(
        default="en",
        description="Language for instructions (e.g., 'en', 'th', 'ja')",
    )
    alternatives: bool = Field(
        default=False,
        description="Whether to return alternative routes",
    )


class PlaceSearchInput(BaseModel):
    """Input schema for place search."""

    query: str = Field(
        ...,
        description="Place search query (e.g., 'restaurants near Shibuya Station')",
    )
    location: str | None = Field(
        None,
        description="Center location as 'lat,lng' for biased search",
    )
    radius: int = Field(
        default=5000,
        description="Search radius in meters (max 50000)",
    )
    language: str = Field(
        default="en",
        description="Language for results",
    )


class PlaceDetailsInput(BaseModel):
    """Input schema for place details."""

    place_id: str = Field(
        ...,
        description="Google Place ID",
    )
    language: str = Field(
        default="en",
        description="Language for results",
    )


# ============ Output Schemas ============


class TransitStop(BaseModel):
    """Information about a transit stop/station."""

    name: str
    location: dict[str, float]  # lat, lng
    arrival_time: str | None = None
    departure_time: str | None = None


class ExitInfo(BaseModel):
    """Parsed exit information from transit station."""

    exit_number: str | None = None
    exit_name: str | None = None
    direction: str | None = None
    landmark: str | None = None


class TransitDetails(BaseModel):
    """Detailed transit information for a step."""

    line_name: str
    line_short_name: str | None = None
    line_color: str | None = None
    vehicle_type: str  # BUS, SUBWAY, TRAIN, TRAM, etc.
    agency_name: str | None = None
    headsign: str | None = None
    departure_stop: TransitStop
    arrival_stop: TransitStop
    num_stops: int
    exit_info: ExitInfo | None = None


class DirectionStep(BaseModel):
    """Single step in directions."""

    instruction: str
    instruction_html: str | None = None
    distance_meters: int
    duration_seconds: int
    travel_mode: str
    start_location: dict[str, float]
    end_location: dict[str, float]
    transit_details: TransitDetails | None = None
    exit_info: ExitInfo | None = None
    maneuver: str | None = None
    polyline: str | None = None


class DirectionLeg(BaseModel):
    """A leg of the journey (origin to destination)."""

    start_address: str
    end_address: str
    start_location: dict[str, float]
    end_location: dict[str, float]
    distance_meters: int
    duration_seconds: int
    departure_time: str | None = None
    arrival_time: str | None = None
    steps: list[DirectionStep]


class DirectionsResult(BaseModel):
    """Result of directions search."""

    origin: str
    destination: str
    mode: str
    legs: list[DirectionLeg]
    total_distance_meters: int
    total_duration_seconds: int
    total_fare: dict | None = None  # For transit
    overview_polyline: str | None = None
    warnings: list[str] | None = None
    copyrights: str | None = None


class PlaceInfo(BaseModel):
    """Information about a place."""

    place_id: str
    name: str
    formatted_address: str | None = None
    location: dict[str, float]
    types: list[str] | None = None
    rating: float | None = None
    user_ratings_total: int | None = None
    price_level: int | None = None
    opening_hours: dict | None = None
    photos: list[str] | None = None
    website: str | None = None
    phone: str | None = None


# ============ Google Maps API Client ============


class GoogleMapsClient(BaseAsyncAPIClient):
    """Async client for Google Maps APIs."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GOOGLE_MAPS_API_KEY
        super().__init__("https://maps.googleapis.com/maps/api")

    async def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {"Accept": "application/json"}

    async def get_directions(
        self,
        origin: str,
        destination: str,
        mode: str = "transit",
        departure_time: str | None = None,
        arrival_time: str | None = None,
        transit_mode: list[str] | None = None,
        language: str = "en",
        alternatives: bool = False,
    ) -> DirectionsResult:
        """Get directions between two locations."""
        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "language": language,
            "alternatives": str(alternatives).lower(),
            "key": self.api_key,
        }

        # Handle departure/arrival time
        if departure_time:
            if departure_time.lower() == "now":
                params["departure_time"] = "now"
            else:
                # Convert ISO to Unix timestamp
                dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
                params["departure_time"] = str(int(dt.timestamp()))
        elif arrival_time:
            dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
            params["arrival_time"] = str(int(dt.timestamp()))
        elif mode == "transit":
            # Transit requires departure or arrival time
            params["departure_time"] = "now"

        if transit_mode:
            params["transit_mode"] = "|".join(transit_mode)

        response = await self.get("/directions/json", params=params)

        if response.get("status") != "OK":
            raise APIClientError(
                f"Directions API error: {response.get('status')}",
                tool_name="GoogleMapsTransitTool",
                details={"error_message": response.get("error_message")},
            )

        return self._parse_directions(response, origin, destination, mode)

    def _parse_directions(
        self,
        response: dict,
        origin: str,
        destination: str,
        mode: str,
    ) -> DirectionsResult:
        """Parse directions response."""
        routes = response.get("routes", [])
        if not routes:
            return DirectionsResult(
                origin=origin,
                destination=destination,
                mode=mode,
                legs=[],
                total_distance_meters=0,
                total_duration_seconds=0,
            )

        # Use first route
        route = routes[0]
        legs = []
        total_distance = 0
        total_duration = 0

        for leg_data in route.get("legs", []):
            steps = []

            for step_data in leg_data.get("steps", []):
                step = self._parse_step(step_data)
                steps.append(step)

            leg = DirectionLeg(
                start_address=leg_data.get("start_address", ""),
                end_address=leg_data.get("end_address", ""),
                start_location=leg_data.get("start_location", {}),
                end_location=leg_data.get("end_location", {}),
                distance_meters=leg_data.get("distance", {}).get("value", 0),
                duration_seconds=leg_data.get("duration", {}).get("value", 0),
                departure_time=leg_data.get("departure_time", {}).get("text"),
                arrival_time=leg_data.get("arrival_time", {}).get("text"),
                steps=steps,
            )
            legs.append(leg)
            total_distance += leg.distance_meters
            total_duration += leg.duration_seconds

        return DirectionsResult(
            origin=origin,
            destination=destination,
            mode=mode,
            legs=legs,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            total_fare=route.get("fare"),
            overview_polyline=route.get("overview_polyline", {}).get("points"),
            warnings=route.get("warnings"),
            copyrights=route.get("copyrights"),
        )

    def _parse_step(self, step_data: dict) -> DirectionStep:
        """Parse a single direction step."""
        html_instructions = step_data.get("html_instructions", "")

        # Parse exit information from HTML instructions
        exit_info = self._parse_exit_info(html_instructions)

        # Parse transit details if present
        transit_details = None
        transit_data = step_data.get("transit_details")
        if transit_data:
            transit_details = self._parse_transit_details(transit_data)

            # Also check transit step instructions for exit info
            if not exit_info.exit_number and transit_details:
                exit_info = self._parse_exit_from_transit(transit_data, html_instructions)

        return DirectionStep(
            instruction=self._strip_html(html_instructions),
            instruction_html=html_instructions,
            distance_meters=step_data.get("distance", {}).get("value", 0),
            duration_seconds=step_data.get("duration", {}).get("value", 0),
            travel_mode=step_data.get("travel_mode", ""),
            start_location=step_data.get("start_location", {}),
            end_location=step_data.get("end_location", {}),
            transit_details=transit_details,
            exit_info=exit_info if exit_info.exit_number else None,
            maneuver=step_data.get("maneuver"),
            polyline=step_data.get("polyline", {}).get("points"),
        )

    def _parse_transit_details(self, transit_data: dict) -> TransitDetails:
        """Parse transit details from step."""
        line = transit_data.get("line", {})
        departure = transit_data.get("departure_stop", {})
        arrival = transit_data.get("arrival_stop", {})

        return TransitDetails(
            line_name=line.get("name", ""),
            line_short_name=line.get("short_name"),
            line_color=line.get("color"),
            vehicle_type=line.get("vehicle", {}).get("type", ""),
            agency_name=line.get("agencies", [{}])[0].get("name") if line.get("agencies") else None,
            headsign=transit_data.get("headsign"),
            departure_stop=TransitStop(
                name=departure.get("name", ""),
                location=departure.get("location", {}),
                departure_time=transit_data.get("departure_time", {}).get("text"),
            ),
            arrival_stop=TransitStop(
                name=arrival.get("name", ""),
                location=arrival.get("location", {}),
                arrival_time=transit_data.get("arrival_time", {}).get("text"),
            ),
            num_stops=transit_data.get("num_stops", 0),
            exit_info=None,
        )

    def _parse_exit_info(self, html_instructions: str) -> ExitInfo:
        """
        Parse exit number and related info from HTML instructions.

        Handles various formats:
        - "Exit 4" / "Exit A" / "Exit 4A"
        - "出口4" / "出口A" (Japanese)
        - "ทางออก 4" (Thai)
        - "Take exit 4 towards..."
        - "Use exit A3 for..."
        """
        exit_info = ExitInfo()

        # Common exit patterns (multiple languages)
        patterns = [
            # English patterns
            r"[Ee]xit\s*([A-Za-z]?\d+[A-Za-z]?)",
            r"[Ee]xit\s*([A-Za-z])\b",
            r"[Tt]ake\s+exit\s*([A-Za-z]?\d+[A-Za-z]?)",
            r"[Uu]se\s+exit\s*([A-Za-z]?\d+[A-Za-z]?)",
            # Japanese patterns
            r"出口\s*([A-Za-z]?\d+[A-Za-z]?)",
            r"出口\s*([A-Za-z])",
            # Thai patterns
            r"ทางออก\s*([A-Za-z]?\d+[A-Za-z]?)",
            # Korean patterns
            r"출구\s*([A-Za-z]?\d+[A-Za-z]?)",
            # Generic numbered exit
            r"[Ee]xit\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)",
        ]

        # Clean HTML tags for parsing
        text = self._strip_html(html_instructions)

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                exit_info.exit_number = f"Exit {match.group(1)}"
                break

        # Try to extract direction/landmark
        direction_patterns = [
            r"(?:towards?|toward|to|direction)\s+([^,\.]+)",
            r"(?:for|to)\s+([^,\.]+)",
        ]

        for pattern in direction_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                direction = match.group(1).strip()
                # Clean up common artifacts
                direction = re.sub(r"<[^>]+>", "", direction)
                if len(direction) > 3 and len(direction) < 100:
                    exit_info.direction = direction
                    break

        return exit_info

    def _parse_exit_from_transit(
        self,
        transit_data: dict,
        html_instructions: str,
    ) -> ExitInfo:
        """Parse exit info specifically from transit step."""
        exit_info = self._parse_exit_info(html_instructions)

        # Check arrival stop name for exit hints
        arrival_stop = transit_data.get("arrival_stop", {}).get("name", "")
        if not exit_info.exit_number:
            # Sometimes exit is in station name
            match = re.search(r"[Ee]xit\s*([A-Za-z]?\d+[A-Za-z]?)", arrival_stop)
            if match:
                exit_info.exit_number = f"Exit {match.group(1)}"

        return exit_info

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags from text."""
        clean = re.sub(r"<[^>]+>", "", html)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    async def search_places(
        self,
        query: str,
        location: str | None = None,
        radius: int = 5000,
        language: str = "en",
    ) -> list[PlaceInfo]:
        """Search for places by text query."""
        params = {
            "query": query,
            "language": language,
            "key": self.api_key,
        }

        if location:
            params["location"] = location
            params["radius"] = radius

        response = await self.get("/place/textsearch/json", params=params)

        if response.get("status") not in ["OK", "ZERO_RESULTS"]:
            raise APIClientError(
                f"Places API error: {response.get('status')}",
                tool_name="GoogleMapsTransitTool",
            )

        places = []
        for result in response.get("results", []):
            places.append(
                PlaceInfo(
                    place_id=result.get("place_id", ""),
                    name=result.get("name", ""),
                    formatted_address=result.get("formatted_address"),
                    location=result.get("geometry", {}).get("location", {}),
                    types=result.get("types"),
                    rating=result.get("rating"),
                    user_ratings_total=result.get("user_ratings_total"),
                    price_level=result.get("price_level"),
                )
            )

        return places

    async def get_place_details(
        self,
        place_id: str,
        language: str = "en",
    ) -> PlaceInfo | None:
        """Get detailed information about a place."""
        params = {
            "place_id": place_id,
            "language": language,
            "fields": "place_id,name,formatted_address,geometry,types,rating,user_ratings_total,price_level,opening_hours,website,formatted_phone_number,photos",
            "key": self.api_key,
        }

        response = await self.get("/place/details/json", params=params)

        if response.get("status") != "OK":
            return None

        result = response.get("result", {})

        # Build photo URLs
        photos = None
        if result.get("photos"):
            photos = [
                f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={p.get('photo_reference')}&key={self.api_key}"
                for p in result.get("photos", [])[:5]
            ]

        return PlaceInfo(
            place_id=result.get("place_id", ""),
            name=result.get("name", ""),
            formatted_address=result.get("formatted_address"),
            location=result.get("geometry", {}).get("location", {}),
            types=result.get("types"),
            rating=result.get("rating"),
            user_ratings_total=result.get("user_ratings_total"),
            price_level=result.get("price_level"),
            opening_hours=result.get("opening_hours"),
            photos=photos,
            website=result.get("website"),
            phone=result.get("formatted_phone_number"),
        )


# ============ LangChain Tools ============


class GoogleMapsDirectionsTool(BaseTool):
    """
    Tool for getting directions and transit information via Google Maps API.

    Use this tool when you need to find how to get from one location to another,
    especially for public transit with detailed station and exit information.

    The tool specifically parses exit numbers from HTML instructions for
    subway/metro stations across multiple languages (English, Japanese, Thai, Korean).
    """

    name: str = "google_maps_directions"
    description: str = """Get directions between two locations with detailed transit information.

Use this tool to find routes via public transit, walking, driving, or bicycling.
For transit, it provides station names, line colors, number of stops, and EXIT NUMBERS.

Input:
- origin: Starting location (address, place name, or 'lat,lng')
- destination: Ending location (address, place name, or 'lat,lng')
- mode: Travel mode ('transit', 'walking', 'driving', 'bicycling')
- departure_time: Optional ISO datetime or 'now'

Example: {"origin": "Shibuya Station", "destination": "Senso-ji Temple", "mode": "transit"}

Returns: Routes with step-by-step instructions including exit numbers at stations."""

    args_schema: type[BaseModel] = DirectionsInput

    async def _arun(
        self,
        origin: str,
        destination: str,
        mode: str = "transit",
        departure_time: str | None = None,
        arrival_time: str | None = None,
        transit_mode: list[str] | None = None,
        language: str = "en",
        alternatives: bool = False,
    ) -> dict[str, Any]:
        """Execute directions search asynchronously."""
        async with GoogleMapsClient() as client:
            result = await client.get_directions(
                origin=origin,
                destination=destination,
                mode=mode,
                departure_time=departure_time,
                arrival_time=arrival_time,
                transit_mode=transit_mode,
                language=language,
                alternatives=alternatives,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class GoogleMapsPlaceSearchTool(BaseTool):
    """
    Tool for searching places via Google Maps Places API.

    Use this tool to find restaurants, attractions, hotels, etc.
    near a specific location or by text query.
    """

    name: str = "google_maps_place_search"
    description: str = """Search for places like restaurants, attractions, hotels by text query.

Input:
- query: Search text (e.g., 'ramen restaurants in Shinjuku')
- location: Optional 'lat,lng' to bias search
- radius: Search radius in meters (default 5000)

Example: {"query": "best sushi restaurants near Tokyo Station", "radius": 1000}

Returns: List of places with names, addresses, ratings, and place IDs."""

    args_schema: type[BaseModel] = PlaceSearchInput

    async def _arun(
        self,
        query: str,
        location: str | None = None,
        radius: int = 5000,
        language: str = "en",
    ) -> list[dict[str, Any]]:
        """Execute place search asynchronously."""
        async with GoogleMapsClient() as client:
            results = await client.search_places(
                query=query,
                location=location,
                radius=radius,
                language=language,
            )
            return [r.model_dump() for r in results]

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class GoogleMapsPlaceDetailsTool(BaseTool):
    """
    Tool for getting detailed place information via Google Maps Places API.

    Use this tool when you have a place_id and need more details like
    opening hours, website, phone number, and photos.
    """

    name: str = "google_maps_place_details"
    description: str = """Get detailed information about a specific place.

Input:
- place_id: Google Place ID (from search results)

Example: {"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"}

Returns: Detailed place info including hours, website, phone, photos."""

    args_schema: type[BaseModel] = PlaceDetailsInput

    async def _arun(
        self,
        place_id: str,
        language: str = "en",
    ) -> dict[str, Any] | None:
        """Execute place details lookup asynchronously."""
        async with GoogleMapsClient() as client:
            result = await client.get_place_details(
                place_id=place_id,
                language=language,
            )
            return result.model_dump() if result else None

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


# Facade class
class GoogleMapsTransitTool:
    """Facade class providing all Google Maps tools."""

    directions = GoogleMapsDirectionsTool()
    place_search = GoogleMapsPlaceSearchTool()
    place_details = GoogleMapsPlaceDetailsTool()

    @classmethod
    def get_all_tools(cls) -> list[BaseTool]:
        """Get all Google Maps tools for LangChain."""
        return [
            cls.directions,
            cls.place_search,
            cls.place_details,
        ]
