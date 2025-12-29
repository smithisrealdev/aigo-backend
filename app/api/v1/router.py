"""API v1 main router - aggregates all domain routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, itinerary, onboarding, tasks, terms, ws

api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(
    auth.router,
    tags=["Authentication"],
)

# Include health check endpoint
api_router.include_router(
    health.router,
    tags=["Health"],
)

# Include itinerary endpoints
api_router.include_router(
    itinerary.router,
    prefix="/itineraries",
    tags=["Itineraries"],
)

# Include task management endpoints (REST)
api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["Tasks"],
)

# Include WebSocket endpoints
api_router.include_router(
    ws.router,
    tags=["WebSocket"],
)

# Include terms and privacy endpoints
api_router.include_router(
    terms.router,
    prefix="/terms",
    tags=["Terms"],
)

# Include onboarding endpoints
api_router.include_router(
    onboarding.router,
    tags=["Onboarding"],
)
