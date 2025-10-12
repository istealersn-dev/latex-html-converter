#!/bin/bash

# Docker Development Helper Script for LaTeX to HTML5 Converter
# This script provides convenient commands for Docker development workflow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="latex-html-converter"
IMAGE_NAME="latex-html-converter"
COMPOSE_FILE="docker-compose.yml"

# Helper functions
print_usage() {
    echo -e "${BLUE}Docker Development Helper for LaTeX to HTML5 Converter${NC}"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image"
    echo "  start       Start development environment with hot-reload"
    echo "  stop        Stop and remove containers"
    echo "  restart     Restart development environment"
    echo "  logs        Show container logs"
    echo "  shell       Open shell in running container"
    echo "  test        Run tests inside container"
    echo "  clean       Clean up containers, images, and volumes"
    echo "  status      Show container status"
    echo "  health      Check service health"
    echo "  help        Show this help message"
    echo ""
}

print_status() {
    echo -e "${BLUE}Container Status:${NC}"
    docker ps -a --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
}

# Build Docker image
build_image() {
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker-compose -f $COMPOSE_FILE build --no-cache
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
}

# Start development environment
start_dev() {
    echo -e "${YELLOW}Starting development environment...${NC}"
    docker-compose -f $COMPOSE_FILE up -d
    echo -e "${GREEN}✓ Development environment started${NC}"
    echo -e "${BLUE}Service available at: http://localhost:8000${NC}"
    echo -e "${BLUE}Health check: http://localhost:8000/api/v1/health${NC}"
}

# Stop containers
stop_containers() {
    echo -e "${YELLOW}Stopping containers...${NC}"
    docker-compose -f $COMPOSE_FILE down
    echo -e "${GREEN}✓ Containers stopped${NC}"
}

# Restart development environment
restart_dev() {
    echo -e "${YELLOW}Restarting development environment...${NC}"
    docker-compose -f $COMPOSE_FILE restart
    echo -e "${GREEN}✓ Development environment restarted${NC}"
}

# Show logs
show_logs() {
    echo -e "${YELLOW}Showing container logs (Ctrl+C to exit)...${NC}"
    docker-compose -f $COMPOSE_FILE logs -f
}

# Open shell in container
open_shell() {
    echo -e "${YELLOW}Opening shell in container...${NC}"
    docker-compose -f $COMPOSE_FILE exec latex-converter /bin/bash
}

# Run tests
run_tests() {
    echo -e "${YELLOW}Running tests inside container...${NC}"
    docker-compose -f $COMPOSE_FILE exec latex-converter poetry run pytest
}

# Clean up everything
clean_all() {
    echo -e "${YELLOW}Cleaning up containers, images, and volumes...${NC}"
    docker-compose -f $COMPOSE_FILE down -v --remove-orphans
    docker system prune -f
    echo -e "${GREEN}✓ Cleanup completed${NC}"
}

# Check service health
check_health() {
    echo -e "${YELLOW}Checking service health...${NC}"
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is healthy${NC}"
    else
        echo -e "${RED}✗ Service is not responding${NC}"
        echo -e "${YELLOW}Check logs with: $0 logs${NC}"
    fi
}

# Main script logic
case "${1:-help}" in
    build)
        build_image
        ;;
    start)
        start_dev
        print_status
        ;;
    stop)
        stop_containers
        ;;
    restart)
        restart_dev
        print_status
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
    test)
        run_tests
        ;;
    clean)
        clean_all
        ;;
    status)
        print_status
        ;;
    health)
        check_health
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        print_usage
        exit 1
        ;;
esac
