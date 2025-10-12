# LaTeX to HTML5 Converter Dockerfile
# Uses official TeXLive image with Python 3.11+ for production deployment

FROM texlive/texlive:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-venv \
    python3-pip \
    curl \
    git \
    make \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for pdflatex as tectonic (since TeXLive has pdflatex but not tectonic)
RUN ln -sf /usr/bin/pdflatex /usr/local/bin/tectonic

# Install LaTeXML and PDF tools
RUN apt-get update && apt-get install -y \
    latexml \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python (if it doesn't exist)
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml ./

# Install Poetry as root
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Configure Poetry
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --only=main --no-interaction --no-ansi --no-root

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY . .

# Create necessary directories and set ownership
RUN mkdir -p /app/uploads /app/outputs /app/logs && \
    chown -R appuser:appuser /app

# Switch to appuser for runtime
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
