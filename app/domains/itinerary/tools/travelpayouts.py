"""Travelpayouts API Tool for affiliate deep links.

This tool integrates with Travelpayouts API to:
- Convert booking URLs to affiliate deep links
- Search for flights with affiliate links
- Search for hotels with affiliate links
- Generate tracking links for commission
"""

import hashlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domains.itinerary.tools.base import APIClientError, BaseAsyncAPIClient

logger = logging.getLogger(__name__)


# ============ Input Schemas ============


class FlightDeepLinkInput(BaseModel):
    """Input schema for flight deep link generation."""

    origin: str = Field(
        ...,
        description="IATA code of origin airport/city",
        min_length=3,
        max_length=3,
    )
    destination: str = Field(
        ...,
        description="IATA code of destination airport/city",
        min_length=3,
        max_length=3,
    )
    departure_date: str = Field(
        ...,
        description="Departure date in YYYY-MM-DD format",
    )
    return_date: str | None = Field(
        None,
        description="Return date in YYYY-MM-DD format (for round trips)",
    )
    adults: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Number of adult passengers",
    )
    cabin_class: str = Field(
        default="Y",
        description="Cabin class: Y (economy), W (premium), C (business), F (first)",
    )
    currency: str = Field(
        default="THB",
        description="Currency for prices",
    )


class HotelDeepLinkInput(BaseModel):
    """Input schema for hotel deep link generation."""

    location: str = Field(
        ...,
        description="City name or location ID",
    )
    check_in_date: str = Field(
        ...,
        description="Check-in date in YYYY-MM-DD format",
    )
    check_out_date: str = Field(
        ...,
        description="Check-out date in YYYY-MM-DD format",
    )
    adults: int = Field(
        default=2,
        ge=1,
        le=9,
        description="Number of adult guests",
    )
    children: int = Field(
        default=0,
        ge=0,
        le=6,
        description="Number of children",
    )
    rooms: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Number of rooms",
    )
    currency: str = Field(
        default="THB",
        description="Currency for prices",
    )
    hotel_id: str | None = Field(
        None,
        description="Specific hotel ID (if known)",
    )


class UrlToAffiliateLinkInput(BaseModel):
    """Input schema for converting URL to affiliate link."""

    original_url: str = Field(
        ...,
        description="Original booking URL to convert to affiliate link",
    )
    link_type: str = Field(
        default="flights",
        description="Type of link: 'flights', 'hotels', 'cars', 'tours'",
    )


class FlightSearchInput(BaseModel):
    """Input schema for flight search with prices."""

    origin: str = Field(
        ...,
        description="IATA code of origin",
        min_length=3,
        max_length=3,
    )
    destination: str = Field(
        ...,
        description="IATA code of destination",
        min_length=3,
        max_length=3,
    )
    departure_date: str = Field(
        ...,
        description="Departure date YYYY-MM-DD",
    )
    return_date: str | None = Field(
        None,
        description="Return date YYYY-MM-DD",
    )
    currency: str = Field(
        default="THB",
        description="Currency code",
    )


# ============ Output Schemas ============


class AffiliateLink(BaseModel):
    """Generated affiliate link with tracking."""

    affiliate_url: str
    original_url: str | None = None
    marker: str
    link_type: str
    tracking_id: str
    expires_at: str | None = None


class FlightPriceResult(BaseModel):
    """Flight price from Travelpayouts."""

    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    price: Decimal
    currency: str
    airline: str
    flight_number: str | None = None
    transfers: int
    duration_minutes: int | None = None
    affiliate_url: str
    found_at: str


class FlightSearchResult(BaseModel):
    """Result of flight search."""

    flights: list[FlightPriceResult]
    origin: str
    destination: str
    search_timestamp: str


class HotelPriceResult(BaseModel):
    """Hotel price from Travelpayouts."""

    hotel_id: str
    hotel_name: str
    location: str
    stars: int | None = None
    price_per_night: Decimal
    total_price: Decimal
    currency: str
    check_in: str
    check_out: str
    room_type: str | None = None
    affiliate_url: str
    rating: float | None = None
    reviews_count: int | None = None


class HotelSearchResult(BaseModel):
    """Result of hotel search."""

    hotels: list[HotelPriceResult]
    location: str
    check_in: str
    check_out: str
    search_timestamp: str


# ============ Travelpayouts API Client ============


class TravelpayoutsClient(BaseAsyncAPIClient):
    """Async client for Travelpayouts API."""

    AVIASALES_SEARCH_URL = "https://www.aviasales.com/search"
    HOTELLOOK_SEARCH_URL = "https://search.hotellook.com/search"
    TP_REDIRECT_URL = "https://tp.media/r"

    def __init__(
        self,
        token: str | None = None,
        marker: str | None = None,
        base_url: str | None = None,
    ):
        self.token = token or settings.TRAVELPAYOUTS_TOKEN
        self.marker = marker or settings.TRAVELPAYOUTS_MARKER
        base_url = base_url or settings.TRAVELPAYOUTS_BASE_URL
        super().__init__(base_url)

    async def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Accept": "application/json",
            "X-Access-Token": self.token,
        }

    def generate_flight_deeplink(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        cabin_class: str = "Y",
        currency: str = "THB",
    ) -> AffiliateLink:
        """Generate affiliate deep link for flight search."""
        # Format date for Aviasales (DDMM)
        dep_date = date.fromisoformat(departure_date)
        dep_str = dep_date.strftime("%d%m")

        # Build search path
        if return_date:
            ret_date = date.fromisoformat(return_date)
            ret_str = ret_date.strftime("%d%m")
            search_path = f"{origin}{dep_str}{destination}{ret_str}{adults}"
        else:
            search_path = f"{origin}{dep_str}{destination}{adults}"

        # Build Aviasales URL
        search_url = f"{self.AVIASALES_SEARCH_URL}/{search_path}"

        # Generate tracking ID
        tracking_id = self._generate_tracking_id(search_url)

        # Build affiliate URL through Travelpayouts redirect
        affiliate_params = {
            "marker": self.marker,
            "u": search_url,
            "p": "2778",  # Aviasales program ID
            "campaign_id": "aigo",
        }

        affiliate_url = f"{self.TP_REDIRECT_URL}?{urlencode(affiliate_params)}"

        return AffiliateLink(
            affiliate_url=affiliate_url,
            original_url=search_url,
            marker=self.marker,
            link_type="flights",
            tracking_id=tracking_id,
        )

    def generate_hotel_deeplink(
        self,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        children: int = 0,
        rooms: int = 1,
        currency: str = "THB",
        hotel_id: str | None = None,
    ) -> AffiliateLink:
        """Generate affiliate deep link for hotel search."""
        # Build Hotellook search URL
        params = {
            "destination": location,
            "checkIn": check_in_date,
            "checkOut": check_out_date,
            "adults": adults,
            "children": children,
            "rooms": rooms,
            "currency": currency.lower(),
        }

        if hotel_id:
            params["hotelId"] = hotel_id

        search_url = f"{self.HOTELLOOK_SEARCH_URL}?{urlencode(params)}"

        # Generate tracking ID
        tracking_id = self._generate_tracking_id(search_url)

        # Build affiliate URL
        affiliate_params = {
            "marker": self.marker,
            "u": search_url,
            "p": "2776",  # Hotellook program ID
            "campaign_id": "aigo",
        }

        affiliate_url = f"{self.TP_REDIRECT_URL}?{urlencode(affiliate_params)}"

        return AffiliateLink(
            affiliate_url=affiliate_url,
            original_url=search_url,
            marker=self.marker,
            link_type="hotels",
            tracking_id=tracking_id,
        )

    def convert_to_affiliate_link(
        self,
        original_url: str,
        link_type: str = "flights",
    ) -> AffiliateLink:
        """Convert any booking URL to affiliate link."""
        tracking_id = self._generate_tracking_id(original_url)

        # Determine program ID based on link type
        program_ids = {
            "flights": "2778",
            "hotels": "2776",
            "cars": "2777",
            "tours": "2779",
        }
        program_id = program_ids.get(link_type, "2778")

        affiliate_params = {
            "marker": self.marker,
            "u": original_url,
            "p": program_id,
            "campaign_id": "aigo",
        }

        affiliate_url = f"{self.TP_REDIRECT_URL}?{urlencode(affiliate_params)}"

        return AffiliateLink(
            affiliate_url=affiliate_url,
            original_url=original_url,
            marker=self.marker,
            link_type=link_type,
            tracking_id=tracking_id,
        )

    def _generate_tracking_id(self, url: str) -> str:
        """Generate unique tracking ID for the link."""
        timestamp = datetime.now().isoformat()
        data = f"{url}:{self.marker}:{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        currency: str = "THB",
    ) -> FlightSearchResult:
        """Search for flight prices via Travelpayouts API."""
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_at": departure_date,
            "currency": currency.lower(),
            "sorting": "price",
            "direct": "false",
            "limit": 10,
            "token": self.token,
        }

        if return_date:
            params["return_at"] = return_date

        try:
            response = await self.get("/v2/prices/latest", params=params)
        except APIClientError:
            # Return empty results if API fails
            logger.warning(f"Travelpayouts flight search failed for {origin}-{destination}")
            return FlightSearchResult(
                flights=[],
                origin=origin.upper(),
                destination=destination.upper(),
                search_timestamp=datetime.now().isoformat(),
            )

        flights = []
        for item in response.get("data", []):
            # Generate affiliate link for this specific flight
            deeplink = self.generate_flight_deeplink(
                origin=origin,
                destination=destination,
                departure_date=item.get("departure_at", departure_date)[:10],
                return_date=item.get("return_at", return_date)[:10] if item.get("return_at") else return_date,
                currency=currency,
            )

            flights.append(
                FlightPriceResult(
                    origin=item.get("origin", origin),
                    destination=item.get("destination", destination),
                    departure_date=item.get("departure_at", departure_date)[:10],
                    return_date=item.get("return_at", "")[:10] if item.get("return_at") else None,
                    price=Decimal(str(item.get("value", 0))),
                    currency=currency.upper(),
                    airline=item.get("gate", "Unknown"),
                    transfers=item.get("transfers", 0),
                    duration_minutes=item.get("duration"),
                    affiliate_url=deeplink.affiliate_url,
                    found_at=item.get("found_at", datetime.now().isoformat()),
                )
            )

        return FlightSearchResult(
            flights=flights,
            origin=origin.upper(),
            destination=destination.upper(),
            search_timestamp=datetime.now().isoformat(),
        )

    async def search_hotels(
        self,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        rooms: int = 1,
        currency: str = "THB",
    ) -> HotelSearchResult:
        """Search for hotel prices via Travelpayouts API."""
        # First need to get location ID
        location_id = await self._get_location_id(location)

        if not location_id:
            return HotelSearchResult(
                hotels=[],
                location=location,
                check_in=check_in_date,
                check_out=check_out_date,
                search_timestamp=datetime.now().isoformat(),
            )

        params = {
            "location": location_id,
            "checkIn": check_in_date,
            "checkOut": check_out_date,
            "adults": adults,
            "limit": 15,
            "currency": currency.lower(),
            "token": self.token,
        }

        try:
            response = await self.get("/v2/lookup.json", params=params)
        except APIClientError:
            logger.warning(f"Travelpayouts hotel search failed for {location}")
            return HotelSearchResult(
                hotels=[],
                location=location,
                check_in=check_in_date,
                check_out=check_out_date,
                search_timestamp=datetime.now().isoformat(),
            )

        hotels = []
        # Calculate nights
        check_in = date.fromisoformat(check_in_date)
        check_out = date.fromisoformat(check_out_date)
        nights = (check_out - check_in).days

        for item in response.get("results", []):
            hotel_id = str(item.get("id", ""))
            deeplink = self.generate_hotel_deeplink(
                location=location,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adults=adults,
                rooms=rooms,
                currency=currency,
                hotel_id=hotel_id,
            )

            price = Decimal(str(item.get("minPrice", 0)))

            hotels.append(
                HotelPriceResult(
                    hotel_id=hotel_id,
                    hotel_name=item.get("name", "Unknown Hotel"),
                    location=location,
                    stars=item.get("stars"),
                    price_per_night=price / nights if nights > 0 else price,
                    total_price=price,
                    currency=currency.upper(),
                    check_in=check_in_date,
                    check_out=check_out_date,
                    room_type=item.get("roomName"),
                    affiliate_url=deeplink.affiliate_url,
                    rating=item.get("rating"),
                    reviews_count=item.get("reviews"),
                )
            )

        return HotelSearchResult(
            hotels=hotels,
            location=location,
            check_in=check_in_date,
            check_out=check_out_date,
            search_timestamp=datetime.now().isoformat(),
        )

    async def _get_location_id(self, location: str) -> str | None:
        """Get Travelpayouts location ID from city name."""
        params = {
            "query": location,
            "locale": "en",
            "token": self.token,
        }

        try:
            response = await self.get("/v1/locations/lookup", params=params)
            locations = response.get("results", {}).get("cities", [])
            if locations:
                return locations[0].get("id")
        except Exception as e:
            logger.warning(f"Failed to get location ID for {location}: {e}")

        return None


# ============ LangChain Tools ============


class TravelpayoutsFlightLinkTool(BaseTool):
    """
    Tool for generating affiliate flight search links.

    Use this tool to create trackable affiliate links for flight bookings
    that earn commission through Travelpayouts.
    """

    name: str = "travelpayouts_flight_link"
    description: str = """Generate affiliate deep link for flight booking.

Use this tool to create an affiliate link for flight search that earns commission.
Input must include origin and destination IATA codes and departure_date.

Example: {"origin": "BKK", "destination": "NRT", "departure_date": "2025-04-01", "adults": 2}

Returns: Affiliate URL for flight booking with tracking."""

    args_schema: type[BaseModel] = FlightDeepLinkInput

    async def _arun(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        cabin_class: str = "Y",
        currency: str = "THB",
    ) -> dict[str, Any]:
        """Generate flight affiliate link."""
        async with TravelpayoutsClient() as client:
            result = client.generate_flight_deeplink(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                adults=adults,
                cabin_class=cabin_class,
                currency=currency,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class TravelpayoutsHotelLinkTool(BaseTool):
    """
    Tool for generating affiliate hotel search links.

    Use this tool to create trackable affiliate links for hotel bookings.
    """

    name: str = "travelpayouts_hotel_link"
    description: str = """Generate affiliate deep link for hotel booking.

Use this tool to create an affiliate link for hotel search that earns commission.
Input must include location, check_in_date, and check_out_date.

Example: {"location": "Tokyo", "check_in_date": "2025-04-01", "check_out_date": "2025-04-08"}

Returns: Affiliate URL for hotel booking with tracking."""

    args_schema: type[BaseModel] = HotelDeepLinkInput

    async def _arun(
        self,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        children: int = 0,
        rooms: int = 1,
        currency: str = "THB",
        hotel_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate hotel affiliate link."""
        async with TravelpayoutsClient() as client:
            result = client.generate_hotel_deeplink(
                location=location,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adults=adults,
                children=children,
                rooms=rooms,
                currency=currency,
                hotel_id=hotel_id,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class TravelpayoutsUrlConverterTool(BaseTool):
    """
    Tool for converting any booking URL to affiliate link.

    Use this tool to convert standard booking URLs into affiliate deep links
    for tracking and commission.
    """

    name: str = "travelpayouts_url_converter"
    description: str = """Convert any booking URL to affiliate link.

Use this tool to convert a booking URL (from Aviasales, Booking.com, etc.)
into an affiliate link with tracking.

Example: {"original_url": "https://www.aviasales.com/search/BKK0104NRT0804", "link_type": "flights"}

Returns: Affiliate URL with tracking marker."""

    args_schema: type[BaseModel] = UrlToAffiliateLinkInput

    async def _arun(
        self,
        original_url: str,
        link_type: str = "flights",
    ) -> dict[str, Any]:
        """Convert URL to affiliate link."""
        async with TravelpayoutsClient() as client:
            result = client.convert_to_affiliate_link(
                original_url=original_url,
                link_type=link_type,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class TravelpayoutsFlightSearchTool(BaseTool):
    """
    Tool for searching flight prices with affiliate links.

    Use this tool to find cheap flights and get affiliate booking links.
    """

    name: str = "travelpayouts_flight_search"
    description: str = """Search for flight prices with affiliate booking links.

Use this tool to find available flights with prices and affiliate links.
Input must include origin and destination IATA codes and departure_date.

Example: {"origin": "BKK", "destination": "NRT", "departure_date": "2025-04-01"}

Returns: List of flights with prices and affiliate booking URLs."""

    args_schema: type[BaseModel] = FlightSearchInput

    async def _arun(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        currency: str = "THB",
    ) -> dict[str, Any]:
        """Search flights with affiliate links."""
        async with TravelpayoutsClient() as client:
            result = await client.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                currency=currency,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


# Facade class
class TravelpayoutsTool:
    """Facade class providing all Travelpayouts tools."""

    flight_link = TravelpayoutsFlightLinkTool()
    hotel_link = TravelpayoutsHotelLinkTool()
    url_converter = TravelpayoutsUrlConverterTool()
    flight_search = TravelpayoutsFlightSearchTool()

    @classmethod
    def get_all_tools(cls) -> list[BaseTool]:
        """Get all Travelpayouts tools for LangChain."""
        return [
            cls.flight_link,
            cls.hotel_link,
            cls.url_converter,
            cls.flight_search,
        ]
