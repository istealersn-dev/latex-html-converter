.PHONY: help lint format type-check file-length test install dev clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run all linting checks
	@echo "🔍 Running linting checks..."
	poetry run ruff check .
	poetry run pylint app/
	poetry run python scripts/check_file_lengths.py 550

format: ## Format code with ruff
	@echo "🎨 Formatting code..."
	poetry run ruff check . --fix
	poetry run ruff format .

type-check: ## Run type checking with mypy
	@echo "🔍 Running type checks..."
	poetry run mypy app/

file-length: ## Check file length limits
	@echo "📏 Checking file lengths..."
	poetry run python scripts/check_file_lengths.py 550

test: ## Run tests
	@echo "🧪 Running tests..."
	poetry run pytest

install: ## Install dependencies
	@echo "📦 Installing dependencies..."
	poetry install

dev: ## Install dev dependencies
	@echo "🛠️ Installing dev dependencies..."
	poetry install --with dev

clean: ## Clean up temporary files
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

check-all: lint type-check file-length test ## Run all checks
	@echo "✅ All checks passed!"
