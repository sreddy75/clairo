# Clairo Backend

FastAPI backend for the Clairo Intelligent Business Advisory Platform.

## Quick Start

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run linting
uv run ruff check .
uv run ruff format --check .

# Run type checking
uv run mypy app
```

## Project Structure

```
backend/
├── app/
│   ├── core/           # Shared kernel (events, exceptions, security)
│   ├── modules/        # Feature modules
│   └── tasks/          # Celery background tasks
├── tests/              # Test suite
├── alembic/            # Database migrations
└── pyproject.toml      # Project configuration
```

See the main project README for full documentation.
