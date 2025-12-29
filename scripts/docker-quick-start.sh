#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 AiGo Backend - Docker Quick Start${NC}"
echo "================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is ready${NC}"

# Remove obsolete version from docker-compose files
echo -e "\n${YELLOW}🔧 Updating docker-compose files...${NC}"
sed -i '' '/^version:/d' docker-compose.yaml 2>/dev/null || true
sed -i '' '/^version:/d' docker-compose.dev.yaml 2>/dev/null || true

# Fix Docker credential issue
echo -e "\n${YELLOW}🔑 Checking Docker credentials...${NC}"
if [ -f ~/.docker/config.json ]; then
    # Backup original
    cp ~/.docker/config.json ~/.docker/config.json.backup
    
    # Remove credsStore if it causes issues
    if grep -q '"credsStore"' ~/.docker/config.json; then
        echo "Fixing credential store..."
        sed -i '' '/"credsStore"/d' ~/.docker/config.json
    fi
fi

# Start PostgreSQL and Redis
echo -e "\n${YELLOW}🚀 Starting PostgreSQL and Redis...${NC}"
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo -e "\n${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
until docker-compose exec -T postgres pg_isready -U aigo -d aigo_db >/dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "\n${GREEN}✅ PostgreSQL is ready${NC}"

# Run migrations
echo -e "\n${YELLOW}🔄 Running database migrations...${NC}"
docker-compose run --rm api poetry run alembic upgrade head

echo -e "\n${GREEN}✅ Migrations complete${NC}"

# Start API server
echo -e "\n${YELLOW}🚀 Starting API server...${NC}"
docker-compose up -d api

# Start Celery worker
echo -e "\n${YELLOW}🔄 Starting Celery worker...${NC}"
docker-compose --profile celery up -d celery-worker

# Show logs
echo -e "\n${GREEN}🎉 All services started!${NC}"
echo "================================="
echo ""
echo -e "${BLUE}📍 API:        ${NC}http://localhost:8000"
echo -e "${BLUE}📖 API Docs:   ${NC}http://localhost:8000/docs"
echo -e "${BLUE}🔄 ReDoc:      ${NC}http://localhost:8000/redoc"
echo -e "${BLUE}💊 Health:     ${NC}http://localhost:8000/health"
echo ""
echo -e "${YELLOW}📋 View logs:${NC}"
echo "   docker-compose logs -f api"
echo ""
echo -e "${YELLOW}🛑 Stop all services:${NC}"
echo "   docker-compose down"
echo ""

# Follow API logs
echo -e "${YELLOW}Showing API logs (Ctrl+C to stop viewing, services keep running)...${NC}"
echo ""
docker-compose logs -f api
