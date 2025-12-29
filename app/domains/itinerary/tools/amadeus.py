"""Amadeus API Tool for fetching real-time flights and hotels.

This tool integrates with the Amadeus Travel API to provide:
- Flight offers search
- Hotel search and offers
- Airport/city autocomplete
- Flight price analysis
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domains.itinerary.tools.base import (
    AuthenticationError,
    BaseAsyncAPIClient,
)

logger = logging.getLogger(__name__)


# ============ Input Schemas ============


class FlightSearchInput(BaseModel):
    """Input schema for flight search."""

    origin: str = Field(
        ...,
        description="IATA code of the origin airport/city (e.g., 'BKK' for Bangkok)",
        min_length=3,
        max_length=3,
    )
    destination: str = Field(
        ...,
        description="IATA code of the destination airport/city (e.g., 'NRT' for Tokyo Narita)",
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
    cabin_class: str | None = Field(
        default="ECONOMY",
        description="Cabin class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of flight offers to return",
    )
    currency: str = Field(
        default="THB",
        description="Currency for prices",
    )


class HotelSearchInput(BaseModel):
    """Input schema for hotel search."""

    city_code: str = Field(
        ...,
        description="IATA city code (e.g., 'TYO' for Tokyo)",
        min_length=3,
        max_length=3,
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
        default=1,
        ge=1,
        le=9,
        description="Number of adult guests",
    )
    rooms: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Number of rooms",
    )
    radius: int = Field(
        default=10,
        description="Search radius in kilometers from city center",
    )
    hotel_stars: list[int] | None = Field(
        default=None,
        description="Filter by star ratings (e.g., [3, 4, 5])",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of hotels to return",
    )
    currency: str = Field(
        default="THB",
        description="Currency for prices",
    )


class AirportSearchInput(BaseModel):
    """Input schema for airport/city search."""

    keyword: str = Field(
        ...,
        description="Search keyword (city name, airport name, or IATA code)",
        min_length=2,
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results",
    )


# ============ Output Schemas ============


class FlightSegment(BaseModel):
    """Single flight segment information."""

    departure_airport: str
    departure_time: str
    arrival_airport: str
    arrival_time: str
    carrier: str
    carrier_name: str | None = None
    flight_number: str
    duration: str
    aircraft: str | None = None


class FlightOffer(BaseModel):
    """Complete flight offer with pricing."""

    offer_id: str
    segments: list[FlightSegment]
    total_price: Decimal
    currency: str
    price_per_adult: Decimal
    cabin_class: str
    stops: int
    total_duration: str
    booking_class: str | None = None
    baggage_info: str | None = None
    refundable: bool = False


class FlightSearchResult(BaseModel):
    """Result of flight search."""

    offers: list[FlightOffer]
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    search_timestamp: str
    dictionaries: dict | None = None  # Carrier names, aircraft codes, etc.


class HotelOffer(BaseModel):
    """Hotel offer with pricing."""

    hotel_id: str
    name: str
    chain_code: str | None = None
    city_code: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    distance_km: float | None = None
    star_rating: int | None = None
    amenities: list[str] | None = None
    room_type: str | None = None
    total_price: Decimal
    price_per_night: Decimal
    currency: str
    check_in: str
    check_out: str
    cancellation_policy: str | None = None
    board_type: str | None = None  # ROOM_ONLY, BREAKFAST, HALF_BOARD, etc.


class HotelSearchResult(BaseModel):
    """Result of hotel search."""

    offers: list[HotelOffer]
    city_code: str
    check_in_date: str
    check_out_date: str
    search_timestamp: str


class AirportInfo(BaseModel):
    """Airport/city information."""

    iata_code: str
    name: str
    city_name: str | None = None
    country_code: str | None = None
    type: str  # AIRPORT, CITY


class AirportSearchResult(BaseModel):
    """Result of airport search."""

    locations: list[AirportInfo]
    keyword: str


# ============ Amadeus API Client ============


class AmadeusClient(BaseAsyncAPIClient):
    """Async client for Amadeus API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ):
        self.client_id = client_id or settings.AMADEUS_CLIENT_ID
        self.client_secret = client_secret or settings.AMADEUS_CLIENT_SECRET
        base_url = base_url or settings.AMADEUS_BASE_URL
        super().__init__(base_url)
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication token."""
        token = await self._ensure_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _ensure_token(self) -> str:
        """Ensure we have a valid access token."""
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at
        ):
            return self._access_token

        # Get new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise AuthenticationError(
                    f"Failed to authenticate with Amadeus: {response.text}",
                    tool_name="AmadeusTool",
                )

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 1799)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            return self._access_token

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        cabin_class: str = "ECONOMY",
        max_results: int = 5,
        currency: str = "THB",
    ) -> FlightSearchResult:
        """Search for flight offers."""
        params = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date,
            "adults": adults,
            "currencyCode": currency,
            "max": max_results,
        }

        if return_date:
            params["returnDate"] = return_date

        if cabin_class:
            params["travelClass"] = cabin_class

        response = await self.get("/v2/shopping/flight-offers", params=params)

        offers = self._parse_flight_offers(response)

        return FlightSearchResult(
            offers=offers,
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            search_timestamp=datetime.now().isoformat(),
            dictionaries=response.get("dictionaries"),
        )

    def _parse_flight_offers(self, response: dict) -> list[FlightOffer]:
        """Parse flight offers from Amadeus response."""
        offers = []
        dictionaries = response.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})

        for data in response.get("data", []):
            segments = []
            total_duration_minutes = 0

            for itinerary in data.get("itineraries", []):
                for segment in itinerary.get("segments", []):
                    carrier_code = segment.get("carrierCode", "")
                    segments.append(
                        FlightSegment(
                            departure_airport=segment["departure"]["iataCode"],
                            departure_time=segment["departure"]["at"],
                            arrival_airport=segment["arrival"]["iataCode"],
                            arrival_time=segment["arrival"]["at"],
                            carrier=carrier_code,
                            carrier_name=carriers.get(carrier_code),
                            flight_number=f"{carrier_code}{segment.get('number', '')}",
                            duration=segment.get("duration", ""),
                            aircraft=segment.get("aircraft", {}).get("code"),
                        )
                    )
                # Parse duration from ISO 8601 (PT2H30M)
                duration_str = itinerary.get("duration", "PT0M")
                total_duration_minutes += self._parse_duration(duration_str)

            price = data.get("price", {})
            total_price = Decimal(price.get("grandTotal", "0"))
            currency = price.get("currency", "THB")

            # Calculate stops (segments - 1 per itinerary)
            stops = max(0, len(segments) - len(data.get("itineraries", [])))

            offers.append(
                FlightOffer(
                    offer_id=data.get("id", ""),
                    segments=segments,
                    total_price=total_price,
                    currency=currency,
                    price_per_adult=Decimal(
                        price.get("pricePerAdult", str(total_price))
                    ),
                    cabin_class=data.get("travelerPricings", [{}])[0]
                    .get("fareDetailsBySegment", [{}])[0]
                    .get("cabin", "ECONOMY"),
                    stops=stops,
                    total_duration=f"{total_duration_minutes // 60}h {total_duration_minutes % 60}m",
                    refundable=price.get("refundable", False),
                )
            )

        return offers

    def _parse_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration to minutes."""
        # Format: PT2H30M or PT45M or PT3H
        import re

        hours = 0
        minutes = 0

        hours_match = re.search(r"(\d+)H", duration)
        if hours_match:
            hours = int(hours_match.group(1))

        minutes_match = re.search(r"(\d+)M", duration)
        if minutes_match:
            minutes = int(minutes_match.group(1))

        return hours * 60 + minutes

    async def search_hotels(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        rooms: int = 1,
        radius: int = 10,
        hotel_stars: list[int] | None = None,
        max_results: int = 10,
        currency: str = "THB",
    ) -> HotelSearchResult:
        """Search for hotel offers."""
        # First get hotels in the city
        hotel_params = {
            "cityCode": city_code.upper(),
            "radius": radius,
            "radiusUnit": "KM",
            "hotelSource": "ALL",
        }

        if hotel_stars:
            hotel_params["ratings"] = ",".join(str(s) for s in hotel_stars)

        hotels_response = await self.get(
            "/v1/reference-data/locations/hotels/by-city",
            params=hotel_params,
        )

        hotels_data = hotels_response.get("data", [])[:max_results]

        if not hotels_data:
            return HotelSearchResult(
                offers=[],
                city_code=city_code.upper(),
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                search_timestamp=datetime.now().isoformat(),
            )

        # Get offers for these hotels
        hotel_ids = [h["hotelId"] for h in hotels_data]

        offer_params = {
            "hotelIds": ",".join(hotel_ids[:20]),  # API limit
            "checkInDate": check_in_date,
            "checkOutDate": check_out_date,
            "adults": adults,
            "roomQuantity": rooms,
            "currency": currency,
        }

        try:
            offers_response = await self.get(
                "/v3/shopping/hotel-offers",
                params=offer_params,
            )
            offers = self._parse_hotel_offers(
                offers_response, hotels_data, check_in_date, check_out_date
            )
        except Exception as e:
            logger.warning(f"Failed to get hotel offers: {e}")
            offers = []

        return HotelSearchResult(
            offers=offers,
            city_code=city_code.upper(),
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            search_timestamp=datetime.now().isoformat(),
        )

    def _parse_hotel_offers(
        self,
        response: dict,
        hotels_data: list[dict],
        check_in: str,
        check_out: str,
    ) -> list[HotelOffer]:
        """Parse hotel offers from Amadeus response."""
        offers = []
        hotels_map = {h["hotelId"]: h for h in hotels_data}

        # Calculate nights
        check_in_date = date.fromisoformat(check_in)
        check_out_date = date.fromisoformat(check_out)
        nights = (check_out_date - check_in_date).days

        for data in response.get("data", []):
            hotel = data.get("hotel", {})
            hotel_id = hotel.get("hotelId", "")
            hotel_info = hotels_map.get(hotel_id, {})

            for offer in data.get("offers", []):
                price = offer.get("price", {})
                total = Decimal(price.get("total", "0"))

                offers.append(
                    HotelOffer(
                        hotel_id=hotel_id,
                        name=hotel.get("name", "Unknown Hotel"),
                        chain_code=hotel.get("chainCode"),
                        city_code=hotel.get("cityCode", ""),
                        latitude=hotel_info.get("geoCode", {}).get("latitude"),
                        longitude=hotel_info.get("geoCode", {}).get("longitude"),
                        address=hotel_info.get("address", {}).get("countryCode"),
                        distance_km=hotel_info.get("distance", {}).get("value"),
                        star_rating=hotel_info.get("rating"),
                        room_type=offer.get("room", {})
                        .get("typeEstimated", {})
                        .get("category"),
                        total_price=total,
                        price_per_night=total / nights if nights > 0 else total,
                        currency=price.get("currency", "THB"),
                        check_in=check_in,
                        check_out=check_out,
                        board_type=offer.get("boardType"),
                    )
                )

        return offers

    async def search_airports(
        self,
        keyword: str,
        max_results: int = 5,
    ) -> AirportSearchResult:
        """Search for airports and cities."""
        params = {
            "subType": "AIRPORT,CITY",
            "keyword": keyword,
            "page[limit]": max_results,
        }

        response = await self.get(
            "/v1/reference-data/locations",
            params=params,
        )

        locations = [
            AirportInfo(
                iata_code=loc.get("iataCode", ""),
                name=loc.get("name", ""),
                city_name=loc.get("address", {}).get("cityName"),
                country_code=loc.get("address", {}).get("countryCode"),
                type=loc.get("subType", "AIRPORT"),
            )
            for loc in response.get("data", [])
        ]

        return AirportSearchResult(
            locations=locations,
            keyword=keyword,
        )


# ============ LangChain Tools ============


class AmadeusFlightSearchTool(BaseTool):
    """
    Tool for searching real-time flight offers via Amadeus API.

    Use this tool when you need to find available flights between two cities/airports.
    Returns flight options with prices, schedules, and airline information.

    Input should include:
    - origin: 3-letter IATA airport/city code (e.g., 'BKK', 'HND')
    - destination: 3-letter IATA airport/city code
    - departure_date: Date in YYYY-MM-DD format
    - Optional: return_date, adults, cabin_class, currency
    """

    name: str = "amadeus_flight_search"
    description: str = """Search for real-time flight offers between two cities.

Use this tool to find available flights with prices and schedules.
Input must include origin (IATA code like 'BKK'), destination (IATA code like 'NRT'),
and departure_date (YYYY-MM-DD format). Optionally include return_date for round trips.

Example input: {"origin": "BKK", "destination": "NRT", "departure_date": "2025-04-01", "adults": 2}"""

    args_schema: type[BaseModel] = FlightSearchInput

    async def _arun(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        cabin_class: str = "ECONOMY",
        max_results: int = 5,
        currency: str = "THB",
    ) -> dict[str, Any]:
        """Execute flight search asynchronously."""
        async with AmadeusClient() as client:
            result = await client.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                adults=adults,
                cabin_class=cabin_class,
                max_results=max_results,
                currency=currency,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class AmadeusHotelSearchTool(BaseTool):
    """
    Tool for searching hotel offers via Amadeus API.

    Use this tool when you need to find available hotels in a city.
    Returns hotel options with prices, ratings, and amenities.

    Input should include:
    - city_code: 3-letter IATA city code (e.g., 'TYO', 'BKK')
    - check_in_date: Date in YYYY-MM-DD format
    - check_out_date: Date in YYYY-MM-DD format
    - Optional: adults, rooms, star ratings, currency
    """

    name: str = "amadeus_hotel_search"
    description: str = """Search for available hotels in a city.

Use this tool to find hotels with prices and availability.
Input must include city_code (IATA code like 'TYO'), check_in_date (YYYY-MM-DD),
and check_out_date (YYYY-MM-DD).

Example input: {"city_code": "TYO", "check_in_date": "2025-04-01", "check_out_date": "2025-04-08", "rooms": 1}"""

    args_schema: type[BaseModel] = HotelSearchInput

    async def _arun(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        rooms: int = 1,
        radius: int = 10,
        hotel_stars: list[int] | None = None,
        max_results: int = 10,
        currency: str = "THB",
    ) -> dict[str, Any]:
        """Execute hotel search asynchronously."""
        async with AmadeusClient() as client:
            result = await client.search_hotels(
                city_code=city_code,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adults=adults,
                rooms=rooms,
                radius=radius,
                hotel_stars=hotel_stars,
                max_results=max_results,
                currency=currency,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class AmadeusAirportSearchTool(BaseTool):
    """
    Tool for searching airports and cities by name or code.

    Use this tool to find IATA codes for airports and cities
    when you need to search for flights.
    """

    name: str = "amadeus_airport_search"
    description: str = """Search for airports and cities to get IATA codes.

Use this tool when you need to find the IATA code for a city or airport.
Input is a keyword (city name, airport name, or partial IATA code).

Example input: {"keyword": "Tokyo"}
Returns: List of matching airports/cities with IATA codes."""

    args_schema: type[BaseModel] = AirportSearchInput

    async def _arun(
        self,
        keyword: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Execute airport search asynchronously."""
        async with AmadeusClient() as client:
            result = await client.search_airports(
                keyword=keyword,
                max_results=max_results,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


# Convenience class combining all Amadeus tools
class AmadeusTool:
    """Facade class providing all Amadeus tools."""

    flight_search = AmadeusFlightSearchTool()
    hotel_search = AmadeusHotelSearchTool()
    airport_search = AmadeusAirportSearchTool()

    @classmethod
    def get_all_tools(cls) -> list[BaseTool]:
        """Get all Amadeus tools for LangChain."""
        return [
            cls.flight_search,
            cls.hotel_search,
            cls.airport_search,
        ]


# Convenience import
import httpx  # noqa: E402
