"""Weather API Tool for fetching forecasts.

This tool integrates with OpenWeatherMap API to provide:
- Current weather conditions
- Weather forecasts for travel dates
- Historical weather data (for better recommendations)
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domains.itinerary.tools.base import APIClientError, BaseAsyncAPIClient

logger = logging.getLogger(__name__)


# ============ Input Schemas ============


class CurrentWeatherInput(BaseModel):
    """Input schema for current weather."""

    location: str = Field(
        ...,
        description="City name (e.g., 'Tokyo', 'Bangkok') or 'lat,lon' coordinates",
    )
    units: str = Field(
        default="metric",
        description="Units: 'metric' (Celsius), 'imperial' (Fahrenheit)",
    )


class WeatherForecastInput(BaseModel):
    """Input schema for weather forecast."""

    location: str = Field(
        ...,
        description="City name or 'lat,lon' coordinates",
    )
    start_date: str = Field(
        ...,
        description="Start date for forecast in YYYY-MM-DD format",
    )
    end_date: str = Field(
        ...,
        description="End date for forecast in YYYY-MM-DD format",
    )
    units: str = Field(
        default="metric",
        description="Units: 'metric' (Celsius), 'imperial' (Fahrenheit)",
    )


class LocationWeatherInput(BaseModel):
    """Input schema for weather at specific coordinates."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    date: str = Field(
        ...,
        description="Date for weather in YYYY-MM-DD format",
    )
    units: str = Field(
        default="metric",
        description="Units for temperature",
    )


# ============ Output Schemas ============


class WeatherCondition(BaseModel):
    """Weather condition details."""

    main: str  # Clear, Clouds, Rain, Snow, etc.
    description: str
    icon: str  # Icon code for UI
    icon_url: str


class CurrentWeather(BaseModel):
    """Current weather data."""

    location: str
    country: str
    latitude: float
    longitude: float
    timestamp: str
    timezone_offset: int

    # Temperature
    temperature: float
    feels_like: float
    temp_min: float
    temp_max: float
    units: str

    # Conditions
    condition: WeatherCondition
    humidity: int  # Percentage
    pressure: int  # hPa
    visibility: int  # meters

    # Wind
    wind_speed: float
    wind_direction: int  # degrees
    wind_gust: float | None = None

    # Additional
    clouds: int  # Cloud coverage percentage
    rain_1h: float | None = None  # Rain volume in last 1h (mm)
    snow_1h: float | None = None  # Snow volume in last 1h (mm)

    # Sun
    sunrise: str | None = None
    sunset: str | None = None

    # Advisory
    uv_index: float | None = None
    air_quality_index: int | None = None
    advisory: str | None = None


class DailyForecast(BaseModel):
    """Daily weather forecast."""

    date: str
    day_name: str

    # Temperature range
    temp_day: float
    temp_night: float
    temp_min: float
    temp_max: float
    feels_like_day: float

    # Conditions
    condition: WeatherCondition
    humidity: int
    pressure: int

    # Wind
    wind_speed: float
    wind_direction: int
    wind_gust: float | None = None

    # Precipitation
    clouds: int
    precipitation_probability: float  # 0-1
    rain_amount: float | None = None  # mm
    snow_amount: float | None = None  # mm

    # Sun
    sunrise: str
    sunset: str
    uv_index: float | None = None

    # Summary
    summary: str | None = None
    advisory: str | None = None


class WeatherForecast(BaseModel):
    """Multi-day weather forecast."""

    location: str
    country: str
    latitude: float
    longitude: float
    units: str
    timezone: str

    daily_forecasts: list[DailyForecast]

    # Summary for the period
    period_summary: str | None = None
    packing_suggestions: list[str] | None = None
    best_days: list[str] | None = None  # Best days for outdoor activities


# ============ Weather API Client ============


class WeatherClient(BaseAsyncAPIClient):
    """Async client for OpenWeatherMap API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.WEATHER_API_KEY
        base_url = base_url or settings.WEATHER_API_BASE_URL
        super().__init__(base_url)

    async def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {"Accept": "application/json"}

    async def get_current_weather(
        self,
        location: str,
        units: str = "metric",
    ) -> CurrentWeather:
        """Get current weather for a location."""
        params = {
            "appid": self.api_key,
            "units": units,
        }

        # Check if location is coordinates
        if "," in location and all(
            part.replace(".", "").replace("-", "").isdigit()
            for part in location.split(",")
        ):
            lat, lon = location.split(",")
            params["lat"] = lat.strip()
            params["lon"] = lon.strip()
        else:
            params["q"] = location

        response = await self.get("/weather", params=params)

        if response.get("cod") != 200:
            raise APIClientError(
                f"Weather API error: {response.get('message', 'Unknown error')}",
                tool_name="WeatherTool",
            )

        return self._parse_current_weather(response, units)

    def _parse_current_weather(self, data: dict, units: str) -> CurrentWeather:
        """Parse current weather response."""
        weather = data.get("weather", [{}])[0]
        main = data.get("main", {})
        wind = data.get("wind", {})
        sys = data.get("sys", {})
        coord = data.get("coord", {})

        # Build icon URL
        icon_code = weather.get("icon", "01d")
        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"

        # Parse sunrise/sunset
        sunrise = None
        sunset = None
        if sys.get("sunrise"):
            sunrise = datetime.fromtimestamp(sys["sunrise"]).isoformat()
        if sys.get("sunset"):
            sunset = datetime.fromtimestamp(sys["sunset"]).isoformat()

        # Generate advisory
        advisory = self._generate_advisory(data, units)

        return CurrentWeather(
            location=data.get("name", "Unknown"),
            country=sys.get("country", ""),
            latitude=coord.get("lat", 0),
            longitude=coord.get("lon", 0),
            timestamp=datetime.fromtimestamp(data.get("dt", 0)).isoformat(),
            timezone_offset=data.get("timezone", 0),
            temperature=main.get("temp", 0),
            feels_like=main.get("feels_like", 0),
            temp_min=main.get("temp_min", 0),
            temp_max=main.get("temp_max", 0),
            units=units,
            condition=WeatherCondition(
                main=weather.get("main", "Unknown"),
                description=weather.get("description", ""),
                icon=icon_code,
                icon_url=icon_url,
            ),
            humidity=main.get("humidity", 0),
            pressure=main.get("pressure", 0),
            visibility=data.get("visibility", 10000),
            wind_speed=wind.get("speed", 0),
            wind_direction=wind.get("deg", 0),
            wind_gust=wind.get("gust"),
            clouds=data.get("clouds", {}).get("all", 0),
            rain_1h=data.get("rain", {}).get("1h"),
            snow_1h=data.get("snow", {}).get("1h"),
            sunrise=sunrise,
            sunset=sunset,
            advisory=advisory,
        )

    def _generate_advisory(self, data: dict, units: str) -> str:
        """Generate weather advisory based on conditions."""
        advisories = []
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        weather_main = weather.get("main", "").lower()

        temp = main.get("temp", 20)
        humidity = main.get("humidity", 50)

        # Temperature advisories
        if units == "metric":
            if temp > 35:
                advisories.append("Extreme heat - stay hydrated and avoid prolonged sun exposure")
            elif temp > 30:
                advisories.append("Hot weather - bring water and sunscreen")
            elif temp < 5:
                advisories.append("Cold weather - dress in warm layers")
            elif temp < 0:
                advisories.append("Freezing conditions - bundle up warmly")
        else:
            if temp > 95:
                advisories.append("Extreme heat - stay hydrated")
            elif temp > 86:
                advisories.append("Hot weather - bring water and sunscreen")
            elif temp < 41:
                advisories.append("Cold weather - dress warmly")
            elif temp < 32:
                advisories.append("Freezing conditions - bundle up")

        # Weather condition advisories
        if weather_main in ["rain", "drizzle"]:
            advisories.append("Bring umbrella or rain gear")
        elif weather_main == "snow":
            advisories.append("Snowy conditions - wear warm, waterproof footwear")
        elif weather_main == "thunderstorm":
            advisories.append("Thunderstorms expected - consider indoor activities")

        # Humidity advisory
        if humidity > 80:
            advisories.append("High humidity - expect sticky conditions")

        return "; ".join(advisories) if advisories else "Good conditions for outdoor activities"

    async def get_forecast(
        self,
        location: str,
        start_date: str,
        end_date: str,
        units: str = "metric",
    ) -> WeatherForecast:
        """Get weather forecast for date range."""
        # First get coordinates if city name provided
        params = {
            "appid": self.api_key,
            "units": units,
        }

        if "," in location and all(
            part.replace(".", "").replace("-", "").isdigit()
            for part in location.split(",")
        ):
            lat, lon = location.split(",")
            params["lat"] = lat.strip()
            params["lon"] = lon.strip()
        else:
            # Get coordinates from city name first
            geo_response = await self._get_coordinates(location)
            if not geo_response:
                raise APIClientError(
                    f"Location not found: {location}",
                    tool_name="WeatherTool",
                )
            params["lat"] = geo_response["lat"]
            params["lon"] = geo_response["lon"]

        # Use 5-day forecast API first (free tier) - more reliable
        # /onecall requires subscription
        try:
            response = await self.get("/forecast", params=params)
            return self._parse_5day_forecast(response, location, start_date, end_date, units)
        except APIClientError as e:
            logger.warning(f"5-day forecast failed: {e}, trying onecall API")
            # Try One Call API as fallback (requires subscription)
            params["exclude"] = "minutely,hourly,alerts"
            try:
                response = await self.get("/onecall", params=params)
                return self._parse_onecall_forecast(response, location, start_date, end_date, units)
            except APIClientError:
                raise

    async def _get_coordinates(self, city: str) -> dict | None:
        """Get coordinates for a city name."""
        params = {
            "q": city,
            "limit": 1,
            "appid": self.api_key,
        }

        # Use geo endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params=params,
            )
            data = response.json()

            if data and len(data) > 0:
                return {
                    "lat": data[0]["lat"],
                    "lon": data[0]["lon"],
                    "name": data[0].get("name", city),
                    "country": data[0].get("country", ""),
                }
            return None

    def _parse_onecall_forecast(
        self,
        response: dict,
        location: str,
        start_date: str,
        end_date: str,
        units: str,
    ) -> WeatherForecast:
        """Parse One Call API response."""
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        daily_forecasts = []

        for day_data in response.get("daily", []):
            day_date = date.fromtimestamp(day_data.get("dt", 0))

            if start <= day_date <= end:
                weather = day_data.get("weather", [{}])[0]
                icon_code = weather.get("icon", "01d")

                daily_forecasts.append(
                    DailyForecast(
                        date=day_date.isoformat(),
                        day_name=day_date.strftime("%A"),
                        temp_day=day_data.get("temp", {}).get("day", 0),
                        temp_night=day_data.get("temp", {}).get("night", 0),
                        temp_min=day_data.get("temp", {}).get("min", 0),
                        temp_max=day_data.get("temp", {}).get("max", 0),
                        feels_like_day=day_data.get("feels_like", {}).get("day", 0),
                        condition=WeatherCondition(
                            main=weather.get("main", "Unknown"),
                            description=weather.get("description", ""),
                            icon=icon_code,
                            icon_url=f"https://openweathermap.org/img/wn/{icon_code}@2x.png",
                        ),
                        humidity=day_data.get("humidity", 0),
                        pressure=day_data.get("pressure", 0),
                        wind_speed=day_data.get("wind_speed", 0),
                        wind_direction=day_data.get("wind_deg", 0),
                        wind_gust=day_data.get("wind_gust"),
                        clouds=day_data.get("clouds", 0),
                        precipitation_probability=day_data.get("pop", 0),
                        rain_amount=day_data.get("rain"),
                        snow_amount=day_data.get("snow"),
                        sunrise=datetime.fromtimestamp(day_data.get("sunrise", 0)).strftime("%H:%M"),
                        sunset=datetime.fromtimestamp(day_data.get("sunset", 0)).strftime("%H:%M"),
                        uv_index=day_data.get("uvi"),
                        summary=day_data.get("summary"),
                    )
                )

        # Generate period summary and packing suggestions
        period_summary, packing = self._generate_period_summary(daily_forecasts, units)

        return WeatherForecast(
            location=location,
            country=response.get("timezone", "").split("/")[0] if response.get("timezone") else "",
            latitude=response.get("lat", 0),
            longitude=response.get("lon", 0),
            units=units,
            timezone=response.get("timezone", "UTC"),
            daily_forecasts=daily_forecasts,
            period_summary=period_summary,
            packing_suggestions=packing,
        )

    def _parse_5day_forecast(
        self,
        response: dict,
        location: str,
        start_date: str,
        end_date: str,
        units: str,
    ) -> WeatherForecast:
        """Parse 5-day/3-hour forecast as fallback."""
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Group by date and average
        daily_data: dict = {}
        city = response.get("city", {})

        for item in response.get("list", []):
            dt = datetime.fromtimestamp(item.get("dt", 0))
            day_date = dt.date()

            if start <= day_date <= end:
                if day_date not in daily_data:
                    daily_data[day_date] = {
                        "temps": [],
                        "humidity": [],
                        "conditions": [],
                        "wind_speeds": [],
                        "pop": [],
                    }

                main = item.get("main", {})
                daily_data[day_date]["temps"].append(main.get("temp", 0))
                daily_data[day_date]["humidity"].append(main.get("humidity", 0))
                daily_data[day_date]["wind_speeds"].append(item.get("wind", {}).get("speed", 0))
                daily_data[day_date]["pop"].append(item.get("pop", 0))
                daily_data[day_date]["conditions"].append(item.get("weather", [{}])[0])

        daily_forecasts = []
        for day_date, data in sorted(daily_data.items()):
            temps = data["temps"]
            # Pick most common condition
            conditions = data["conditions"]
            condition = max(conditions, key=lambda c: conditions.count(c)) if conditions else {}
            icon_code = condition.get("icon", "01d")

            daily_forecasts.append(
                DailyForecast(
                    date=day_date.isoformat(),
                    day_name=day_date.strftime("%A"),
                    temp_day=sum(temps) / len(temps) if temps else 0,
                    temp_night=min(temps) if temps else 0,
                    temp_min=min(temps) if temps else 0,
                    temp_max=max(temps) if temps else 0,
                    feels_like_day=sum(temps) / len(temps) if temps else 0,
                    condition=WeatherCondition(
                        main=condition.get("main", "Unknown"),
                        description=condition.get("description", ""),
                        icon=icon_code,
                        icon_url=f"https://openweathermap.org/img/wn/{icon_code}@2x.png",
                    ),
                    humidity=int(sum(data["humidity"]) / len(data["humidity"])) if data["humidity"] else 0,
                    pressure=1013,
                    wind_speed=sum(data["wind_speeds"]) / len(data["wind_speeds"]) if data["wind_speeds"] else 0,
                    wind_direction=0,
                    clouds=0,
                    precipitation_probability=max(data["pop"]) if data["pop"] else 0,
                    sunrise=datetime.fromtimestamp(city.get("sunrise", 0)).strftime("%H:%M") if city.get("sunrise") else "06:00",
                    sunset=datetime.fromtimestamp(city.get("sunset", 0)).strftime("%H:%M") if city.get("sunset") else "18:00",
                )
            )

        period_summary, packing = self._generate_period_summary(daily_forecasts, units)

        return WeatherForecast(
            location=city.get("name", location),
            country=city.get("country", ""),
            latitude=city.get("coord", {}).get("lat", 0),
            longitude=city.get("coord", {}).get("lon", 0),
            units=units,
            timezone="UTC",
            daily_forecasts=daily_forecasts,
            period_summary=period_summary,
            packing_suggestions=packing,
        )

    def _generate_period_summary(
        self,
        forecasts: list[DailyForecast],
        units: str,
    ) -> tuple[str, list[str]]:
        """Generate summary and packing suggestions for the forecast period."""
        if not forecasts:
            return "No forecast data available", []

        # Calculate averages
        avg_temp = sum(f.temp_day for f in forecasts) / len(forecasts)
        max_temp = max(f.temp_max for f in forecasts)
        min_temp = min(f.temp_min for f in forecasts)
        avg_rain_prob = sum(f.precipitation_probability for f in forecasts) / len(forecasts)

        # Count rainy days
        rainy_days = sum(1 for f in forecasts if f.precipitation_probability > 0.5)

        # Build summary
        temp_unit = "°C" if units == "metric" else "°F"
        summary_parts = [
            f"Temperature ranging from {min_temp:.0f}{temp_unit} to {max_temp:.0f}{temp_unit}",
            f"Average: {avg_temp:.0f}{temp_unit}",
        ]

        if rainy_days > 0:
            summary_parts.append(f"{rainy_days} day(s) with rain expected")

        summary = ". ".join(summary_parts)

        # Generate packing suggestions
        packing = []

        if units == "metric":
            if max_temp > 30:
                packing.extend(["Light, breathable clothing", "Sunscreen", "Hat"])
            if min_temp < 15:
                packing.append("Light jacket or sweater")
            if min_temp < 5:
                packing.extend(["Warm coat", "Gloves", "Scarf"])
        else:
            if max_temp > 86:
                packing.extend(["Light, breathable clothing", "Sunscreen", "Hat"])
            if min_temp < 59:
                packing.append("Light jacket or sweater")
            if min_temp < 41:
                packing.extend(["Warm coat", "Gloves", "Scarf"])

        if avg_rain_prob > 0.3:
            packing.extend(["Umbrella", "Waterproof jacket"])

        # Always useful
        packing.append("Comfortable walking shoes")

        return summary, packing


# ============ LangChain Tools ============


class WeatherCurrentTool(BaseTool):
    """
    Tool for getting current weather conditions.

    Use this tool to get the current weather at a destination
    to help users prepare for immediate conditions.
    """

    name: str = "weather_current"
    description: str = """Get current weather conditions for a location.

Use this tool to check current weather including temperature, conditions, humidity, and wind.
Input is a city name (e.g., 'Tokyo') or coordinates ('35.6762,139.6503').

Example: {"location": "Bangkok", "units": "metric"}

Returns: Current temperature, conditions, humidity, wind, and advisory."""

    args_schema: type[BaseModel] = CurrentWeatherInput

    async def _arun(
        self,
        location: str,
        units: str = "metric",
    ) -> dict[str, Any]:
        """Get current weather asynchronously."""
        async with WeatherClient() as client:
            result = await client.get_current_weather(
                location=location,
                units=units,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


class WeatherForecastTool(BaseTool):
    """
    Tool for getting weather forecast for travel dates.

    Use this tool when planning activities to know expected weather
    during the trip. Helps with activity planning and packing advice.
    """

    name: str = "weather_forecast"
    description: str = """Get weather forecast for travel dates.

Use this tool to get daily weather forecasts for trip planning.
Input must include location, start_date and end_date (YYYY-MM-DD format).

Example: {"location": "Tokyo", "start_date": "2025-04-01", "end_date": "2025-04-07"}

Returns: Daily forecasts with temperature, conditions, rain probability, and packing suggestions."""

    args_schema: type[BaseModel] = WeatherForecastInput

    async def _arun(
        self,
        location: str,
        start_date: str,
        end_date: str,
        units: str = "metric",
    ) -> dict[str, Any]:
        """Get weather forecast asynchronously."""
        async with WeatherClient() as client:
            result = await client.get_forecast(
                location=location,
                start_date=start_date,
                end_date=end_date,
                units=units,
            )
            return result.model_dump()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync run not supported."""
        raise NotImplementedError("Use async version with _arun")


# Facade class
class WeatherTool:
    """Facade class providing all Weather tools."""

    current = WeatherCurrentTool()
    forecast = WeatherForecastTool()

    @classmethod
    def get_all_tools(cls) -> list[BaseTool]:
        """Get all Weather tools for LangChain."""
        return [
            cls.current,
            cls.forecast,
        ]
