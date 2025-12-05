# LaTeX to HTML5 Converter Dockerfile
# Uses official TeXLive image with Python 3.11+ for production deployment

FROM texlive/texlive:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install comprehensive LaTeX packages and system dependencies
# NOTE: texlive-full creates a large image (~4GB). For production optimization, consider:
# - Using a smaller base image like texlive/texlive:TL2023-historic
# - Installing only required packages instead of texlive-full
# - Multi-stage build to separate build dependencies from runtime
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
    texlive-full \
    texlive-science \
    texlive-publishers \
    texlive-bibtex-extra \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-latex-recommended \
    latexml \
    poppler-utils \
    dvisvgm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Create non-root user early for security
RUN useradd --create-home --shell /bin/bash appuser

# Configure tlmgr for package management (run as root but configure for user)
RUN tlmgr init-usertree && \
    tlmgr option repository https://mirror.ctan.org/systems/texlive/tlnet && \
    tlmgr update --self

# Create symbolic link for pdflatex as tectonic (since TeXLive has pdflatex but not tectonic)
RUN ln -sf /usr/bin/pdflatex /usr/local/bin/tectonic

# Create symbolic link for python (if it doesn't exist)
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml ./

# Install Poetry system-wide (accessible to all users)
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    mv /root/.local /usr/local/poetry
ENV PATH="/usr/local/poetry/bin:$PATH"

# Configure Poetry to not create virtualenvs
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --only=main --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# Create necessary directories and set ownership
RUN mkdir -p /app/uploads /app/outputs /app/logs && \
    chown -R appuser:appuser /app

# Switch to appuser for runtime
USER appuser

# Expose port
EXPOSE 8000

# Health check using Python instead of curl (reduces dependencies)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/healthz').read()" || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
