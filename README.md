# AiGo Backend

AI-powered Travel Itinerary Planning Backend built with FastAPI and Python 3.12.

## 🏗️ Project Structure (DDD-based)

```
aigo-backend/
├── app/
│   ├── api/                    # API Layer
│   │   └── v1/
│   │       ├── endpoints/      # Route handlers
│   │       └── router.py       # Main API router
│   ├── core/                   # Core settings & utilities
│   │   ├── config.py           # Pydantic Settings
│   │   └── security.py         # Auth utilities
│   ├── domains/                # Domain Layer (DDD)
│   │   └── itinerary/
│   │       ├── models.py       # SQLAlchemy models
│   │       ├── schemas.py      # Pydantic schemas
│   │       ├── repository.py   # Data access layer
│   │       └── services.py     # Business logic
│   ├── infra/                  # Infrastructure Layer
│   │   ├── database.py         # PostgreSQL setup
│   │   └── redis.py            # Redis setup
│   └── main.py                 # Application entry point
├── tests/                      # Test suite
├── .env.example                # Environment template
├── pyproject.toml              # Poetry configuration
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL
- Redis

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd aigo-backend
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the server**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## 🔧 Configuration

All configuration is managed through environment variables. See `.env.example` for available options.

### Required API Keys

- **Amadeus API**: For flight and hotel search
  - Sign up at: https://developers.amadeus.com/
- **Google Maps API**: For location and places services
  - Get API key at: https://console.cloud.google.com/
- **OpenAI API**: For AI-powered itinerary generation
  - Get API key at: https://platform.openai.com/
- **OpenWeatherMap API**: For weather forecasts and conditions
  - Sign up at: https://openweathermap.org/api
  - Get API key from: https://home.openweathermap.org/api_keys
  - Supports Current Weather and 5-day/3-hour Forecast endpoints

## 📝 API Endpoints

### Health Check
- `GET /api/v1/health` - Health check
- `GET /api/v1/` - API info

### Itineraries
- `POST /api/v1/itineraries` - Create itinerary
- `GET /api/v1/itineraries` - List itineraries (paginated)
- `GET /api/v1/itineraries/{id}` - Get itinerary
- `PATCH /api/v1/itineraries/{id}` - Update itinerary
- `DELETE /api/v1/itineraries/{id}` - Delete itinerary

### Activities
- `POST /api/v1/itineraries/{id}/activities` - Add activity
- `PATCH /api/v1/itineraries/activities/{id}` - Update activity
- `DELETE /api/v1/itineraries/activities/{id}` - Delete activity

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_itinerary.py -v
```

## 🛠️ Development

```bash
# Format code
poetry run ruff format .

# Lint code
poetry run ruff check .

# Type checking
poetry run mypy app
```

## 📄 License

MIT License
