#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🗄️  Setting up PostgreSQL database for AiGo...${NC}"

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values if not in .env
POSTGRES_USER=${POSTGRES_USER:-aigo}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-aigo_password}
POSTGRES_DB=${POSTGRES_DB:-aigo_db}
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}

echo -e "\n${YELLOW}Database Configuration:${NC}"
echo "  User:     $POSTGRES_USER"
echo "  Database: $POSTGRES_DB"
echo "  Host:     $POSTGRES_HOST:$POSTGRES_PORT"
echo ""

# Create user if not exists
echo -e "${YELLOW}Creating database user...${NC}"
psql postgres -c "CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';" 2>/dev/null || echo "User already exists"

# Grant superuser privileges (needed for extensions)
psql postgres -c "ALTER USER ${POSTGRES_USER} WITH SUPERUSER;"

# Create database if not exists
echo -e "${YELLOW}Creating database...${NC}"
psql postgres -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};" 2>/dev/null || echo "Database already exists"

# Grant privileges
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};"

echo -e "\n${GREEN}✅ Database setup complete!${NC}"
echo -e "${BLUE}📊 Connection string:${NC}"
echo "   postgresql://${POSTGRES_USER}:***@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo ""
echo -e "${YELLOW}💡 Test connection with:${NC}"
echo "   psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'SELECT version();'"
echo ""
