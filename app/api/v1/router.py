"""API v1 main router - aggregates all domain routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, itinerary, tasks, ws

api_router = APIRouter()

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
