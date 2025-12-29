#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 AiGo Backend - Quick Start${NC}"
echo "================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if PostgreSQL is running
check_postgres() {
    pg_isready -h localhost -p 5432 >/dev/null 2>&1
}

# Function to check if Redis is running
check_redis() {
    redis-cli ping >/dev/null 2>&1
}

# 1. Check dependencies
echo -e "\n${YELLOW}📦 Checking dependencies...${NC}"

if ! command_exists poetry; then
    echo -e "${RED}❌ Poetry not found. Installing...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

if ! command_exists psql; then
    echo -e "${RED}❌ PostgreSQL not found.${NC}"
    echo "Please install PostgreSQL:"
    echo "  brew install postgresql@16"
    exit 1
fi

if ! command_exists redis-cli; then
    echo -e "${RED}❌ Redis not found.${NC}"
    echo "Please install Redis:"
    echo "  brew install redis"
    exit 1
fi

echo -e "${GREEN}✅ All dependencies found${NC}"

# 2. Start PostgreSQL and Redis if not running
echo -e "\n${YELLOW}🔧 Starting services...${NC}"

if ! check_postgres; then
    echo "Starting PostgreSQL..."
    brew services start postgresql@16
    sleep 3
fi

if ! check_redis; then
    echo "Starting Redis..."
    brew services start redis
    sleep 2
fi

echo -e "${GREEN}✅ Services running${NC}"

# 3. Setup database
echo -e "\n${YELLOW}🗄️  Setting up database...${NC}"

# Check if database exists
if ! psql postgres -lqt | cut -d \| -f 1 | grep -qw aigo_db; then
    echo "Creating database and user..."
    
    # Create user
    psql postgres -c "CREATE USER aigo WITH PASSWORD 'aigo_password';" 2>/dev/null || true
    psql postgres -c "ALTER USER aigo WITH SUPERUSER;"
    
    # Create database
    psql postgres -c "CREATE DATABASE aigo_db OWNER aigo;"
    psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE aigo_db TO aigo;"
    
    echo -e "${GREEN}✅ Database created${NC}"
else
    echo -e "${GREEN}✅ Database already exists${NC}"
fi

# 4. Install Python dependencies
echo -e "\n${YELLOW}📚 Installing Python packages...${NC}"
poetry install --no-root

# 5. Check .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}📝 Creating .env file...${NC}"
    
    if [ -f .env.example ]; then
        cp .env.example .env
    fi
    
    # Generate secure secret key
    SECRET_KEY=$(openssl rand -base64 32)
    
    if [ -f .env ]; then
        sed -i '' "s/your-super-secret-key-change-in-production-min-32-chars/$SECRET_KEY/" .env
    fi
    
    echo -e "${GREEN}✅ .env file created${NC}"
    echo -e "${YELLOW}⚠️  Please update API keys in .env file if needed${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# 6. Run migrations
echo -e "\n${YELLOW}🔄 Running database migrations...${NC}"
poetry run alembic upgrade head
echo -e "${GREEN}✅ Migrations complete${NC}"

# 7. Start the application
echo -e "\n${GREEN}🎉 Setup complete! Starting server...${NC}"
echo "================================="
echo ""
echo -e "${BLUE}📍 API:        ${NC}http://localhost:8000"
echo -e "${BLUE}📖 API Docs:   ${NC}http://localhost:8000/docs"
echo -e "${BLUE}🔄 ReDoc:      ${NC}http://localhost:8000/redoc"
echo -e "${BLUE}💊 Health:     ${NC}http://localhost:8000/health"
echo ""
echo -e "${YELLOW}💡 Tip: Open another terminal and run 'make start-celery' for background tasks${NC}"
echo -e "${YELLOW}🛑 Press Ctrl+C to stop the server${NC}"
echo ""

# Start server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
