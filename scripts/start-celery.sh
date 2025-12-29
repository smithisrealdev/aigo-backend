#!/bin/bash
set -e

# Colors for output
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔄 Starting Celery Worker...${NC}"
echo ""
echo -e "${YELLOW}💡 This worker handles background tasks:${NC}"
echo "   • Itinerary generation"
echo "   • Smart re-planning"
echo "   • Real-time progress updates"
echo ""
echo -e "${YELLOW}🛑 Press Ctrl+C to stop${NC}"
echo ""

# Start Celery worker
poetry run celery -A app.infra.celery_app worker \
    --loglevel=info \
    --queues=default,itinerary,replan \
    --concurrency=2 \
    --pool=solo
