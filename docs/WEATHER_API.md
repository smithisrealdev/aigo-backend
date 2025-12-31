# Weather API Integration - MCP Tool Contract Documentation

## Overview

This document describes the Weather API integration using OpenWeatherMap and the MCP (Model Context Protocol) Tool Contract implementation for the AiGo Backend.

## API Provider

**OpenWeatherMap API**
- Website: https://openweathermap.org/api
- Sign up: https://openweathermap.org/api
- API Key Management: https://home.openweathermap.org/api_keys
- Documentation: https://openweathermap.org/api/one-call-api

## MCP Tool Contract

The Weather API integration provides two LangChain-compatible tools following the MCP Tool Contract pattern:

### 1. `get_current_weather` Tool

**Tool Name:** `weather_current`

**Description:** Get current weather conditions for a location.

**Input Schema:**
```python
{
  "location": str,  # Required: City name (e.g., "Tokyo") or coordinates ("35.6762,139.6503")
  "units": str      # Optional: "metric" (Celsius) or "imperial" (Fahrenheit), default="metric"
}
```

**Example Usage:**
```python
# Using the tool directly
from app.domains.itinerary.tools.weather import WeatherTool

result = await WeatherTool.current._arun(
    location="Bangkok",
    units="metric"
)

# Example input
{
  "location": "Bangkok",
  "units": "metric"
}

# Example output (simplified)
{
  "location": "Bangkok",
  "country": "TH",
  "latitude": 13.7563,
  "longitude": 100.5018,
  "temperature": 32.5,
  "feels_like": 37.2,
  "condition": {
    "main": "Clear",
    "description": "clear sky",
    "icon": "01d",
    "icon_url": "https://openweathermap.org/img/wn/01d@2x.png"
  },
  "humidity": 65,
  "wind_speed": 3.5,
  "advisory": "Hot weather - bring water and sunscreen"
}
```

**Output Schema:**
```python
CurrentWeather {
  location: str
  country: str
  latitude: float
  longitude: float
  timestamp: str
  timezone_offset: int
  temperature: float
  feels_like: float
  temp_min: float
  temp_max: float
  units: str
  condition: WeatherCondition {
    main: str
    description: str
    icon: str
    icon_url: str
  }
  humidity: int
  pressure: int
  visibility: int
  wind_speed: float
  wind_direction: int
  wind_gust: float | None
  clouds: int
  rain_1h: float | None
  snow_1h: float | None
  sunrise: str | None
  sunset: str | None
  uv_index: float | None
  air_quality_index: int | None
  advisory: str | None
}
```

**Use Cases:**
- Get immediate weather conditions for trip preparation
- Check current conditions before activities
- Provide real-time weather updates to travelers

### 2. `get_weather_forecast` Tool

**Tool Name:** `weather_forecast`

**Description:** Get weather forecast for travel dates to help with activity planning.

**Input Schema:**
```python
{
  "location": str,     # Required: City name or coordinates
  "start_date": str,   # Required: YYYY-MM-DD format
  "end_date": str,     # Required: YYYY-MM-DD format
  "units": str         # Optional: "metric" or "imperial", default="metric"
}
```

**Example Usage:**
```python
# Using the tool directly
from app.domains.itinerary.tools.weather import WeatherTool

result = await WeatherTool.forecast._arun(
    location="Tokyo",
    start_date="2025-04-01",
    end_date="2025-04-07",
    units="metric"
)

# Example input
{
  "location": "Tokyo",
  "start_date": "2025-04-01",
  "end_date": "2025-04-07",
  "units": "metric"
}

# Example output (simplified)
{
  "location": "Tokyo",
  "country": "JP",
  "latitude": 35.6762,
  "longitude": 139.6503,
  "units": "metric",
  "timezone": "Asia/Tokyo",
  "period_summary": "Temperature ranging from 8°C to 18°C. Average: 13°C",
  "packing_suggestions": [
    "Light jacket or sweater",
    "Comfortable walking shoes"
  ],
  "daily_forecasts": [
    {
      "date": "2025-04-01",
      "day_name": "Tuesday",
      "temp_day": 15.0,
      "temp_night": 10.0,
      "temp_min": 8.0,
      "temp_max": 18.0,
      "condition": {
        "main": "Clouds",
        "description": "scattered clouds",
        "icon": "03d"
      },
      "precipitation_probability": 0.2,
      "sunrise": "05:30",
      "sunset": "18:00"
    }
    // ... more daily forecasts
  ]
}
```

**Output Schema:**
```python
WeatherForecast {
  location: str
  country: str
  latitude: float
  longitude: float
  units: str
  timezone: str
  daily_forecasts: list[DailyForecast] {
    date: str
    day_name: str
    temp_day: float
    temp_night: float
    temp_min: float
    temp_max: float
    feels_like_day: float
    condition: WeatherCondition
    humidity: int
    pressure: int
    wind_speed: float
    wind_direction: int
    wind_gust: float | None
    clouds: int
    precipitation_probability: float  # 0-1
    rain_amount: float | None
    snow_amount: float | None
    sunrise: str
    sunset: str
    uv_index: float | None
    summary: str | None
    advisory: str | None
  }
  period_summary: str | None
  packing_suggestions: list[str] | None
  best_days: list[str] | None
}
```

**Use Cases:**
- Plan activities based on weather forecasts
- Generate packing lists based on expected conditions
- Recommend best days for outdoor activities
- Provide weather context for itinerary planning

## API Endpoints Used

### 1. Current Weather API
- **Endpoint:** `GET /weather`
- **Documentation:** https://openweathermap.org/current
- **Parameters:**
  - `q`: City name (e.g., "Bangkok,TH")
  - `lat` & `lon`: Geographic coordinates
  - `units`: metric/imperial
  - `appid`: API key

### 2. 5-Day Forecast API
- **Endpoint:** `GET /forecast`
- **Documentation:** https://openweathermap.org/forecast5
- **Parameters:**
  - `q`: City name
  - `lat` & `lon`: Geographic coordinates
  - `units`: metric/imperial
  - `appid`: API key

### 3. One Call API (Optional)
- **Endpoint:** `GET /onecall`
- **Documentation:** https://openweathermap.org/api/one-call-api
- **Note:** Requires separate subscription but provides better forecast data

## Configuration

Add the following to your `.env` file:

```bash
# Weather API (OpenWeatherMap)
WEATHER_API_KEY=your_openweathermap_api_key
WEATHER_API_BASE_URL=https://api.openweathermap.org/data/2.5
```

## Integration with LangGraph

The Weather tools are integrated into the itinerary planning workflow through LangGraph:

```python
from app.domains.itinerary.tools import WeatherTool

# Get all weather tools
weather_tools = WeatherTool.get_all_tools()

# Use in LangGraph agent
agent = create_react_agent(
    model=llm,
    tools=[
        *weather_tools,
        # ... other tools
    ]
)
```

The tools are used in the Data Gathering step of the planner workflow to fetch weather information for the travel dates and destination.

## Testing

Run the comprehensive test script:

```bash
python scripts/test_weather_api.py
```

The test script will:
1. Verify API credentials
2. Test current weather endpoint with multiple locations
3. Test weather forecast endpoint with date ranges
4. Test LangChain tool integration
5. Display MCP Tool Contract information

## Error Handling

The implementation includes comprehensive error handling:

- **Authentication Errors:** Clear message when API key is missing or invalid
- **Rate Limiting:** Proper handling of API rate limits
- **Network Errors:** Retry logic for transient failures
- **Fallback Support:** Generates estimated weather data when API is unavailable
- **Location Not Found:** Clear error messages for invalid locations

## Advisory System

The Weather API includes an intelligent advisory system that generates contextual advice based on:

- Temperature extremes (heat/cold warnings)
- Precipitation (rain/snow alerts)
- Humidity levels
- Weather conditions (thunderstorms, etc.)

Example advisories:
- "Hot weather - bring water and sunscreen"
- "Bring umbrella or rain gear"
- "High humidity - expect sticky conditions"

## Packing Suggestions

The forecast tool automatically generates packing suggestions based on:

- Temperature range
- Precipitation probability
- Weather conditions
- Duration of stay

Example suggestions:
- "Light, breathable clothing"
- "Sunscreen"
- "Umbrella"
- "Light jacket or sweater"
- "Warm coat"

## Best Practices

1. **Cache Results:** Weather data is relatively stable, consider caching for 15-30 minutes
2. **Location Validation:** Validate location before making API calls
3. **Error Handling:** Always handle potential API failures gracefully
4. **Rate Limiting:** Be aware of API rate limits (60 calls/minute for free tier)
5. **Units Consistency:** Use consistent units throughout the application

## API Limits

**Free Tier:**
- 60 calls/minute
- 1,000,000 calls/month
- Current weather + 5-day/3-hour forecast

**Paid Tiers:**
- Higher rate limits
- One Call API access (better forecasts)
- Historical data access
- Air quality data

## Support and Resources

- **API Documentation:** https://openweathermap.org/api
- **API Status:** https://openweathermap.org/api-status
- **Support:** https://openweathermap.org/faq
- **Pricing:** https://openweathermap.org/price

## Implementation Files

- **Tool Implementation:** `app/domains/itinerary/tools/weather.py`
- **Configuration:** `app/core/config.py`
- **Integration:** `app/domains/itinerary/services/planner_graph.py`
- **Test Script:** `scripts/test_weather_api.py`
- **Documentation:** This file

---

Last Updated: 2025-12-31
Version: 1.0
