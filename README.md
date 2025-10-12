# LaTeX to HTML5 Converter

A high-performance service for converting LaTeX documents to HTML5 with advanced asset conversion capabilities.

## 🚀 Quick Start with Docker (Recommended)

The easiest way to run the LaTeX to HTML5 Converter is using Docker:

### Prerequisites
- Docker and Docker Compose installed
- Git (to clone the repository)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd latex-to-html-converter
```

### 2. Start with Docker
```bash
# Build and start the service
./scripts/docker-dev.sh build
./scripts/docker-dev.sh start

# Check service health
./scripts/docker-dev.sh health
```

### 3. Test the API
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Convert a LaTeX file
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.zip"
```

### 4. Development Commands
```bash
# View logs
./scripts/docker-dev.sh logs

# Open shell in container
./scripts/docker-dev.sh shell

# Run tests
./scripts/docker-dev.sh test

# Stop service
./scripts/docker-dev.sh stop
```

## 📋 Features

- **LaTeX Compilation**: Uses Tectonic for reliable LaTeX compilation
- **HTML Conversion**: LaTeXML for high-quality TeX to HTML conversion
- **Asset Conversion**: TikZ diagrams and PDF figures to SVG
- **MathJax Integration**: Mathematical expressions with MathJax
- **Background Processing**: Asynchronous job processing with status tracking
- **RESTful API**: Clean REST API for integration
- **Docker Ready**: Full Docker support for development and production

## 🏗️ Architecture

The converter uses a multi-stage pipeline:

1. **Archive Extraction**: Supports ZIP, TAR, and TAR.GZ files
2. **LaTeX Compilation**: Tectonic for PDF generation
3. **HTML Conversion**: LaTeXML for HTML generation
4. **Asset Processing**: TikZ/PDF to SVG conversion
5. **Post-processing**: HTML cleanup and MathJax integration

## 🔧 Development

### Local Development (without Docker)
```bash
# Install dependencies
poetry install

# Start the service
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Development
```bash
# Start development environment
./scripts/docker-dev.sh start

# View logs
./scripts/docker-dev.sh logs

# Run tests
./scripts/docker-dev.sh test
```

## 📚 Documentation

- **[DOCKER.md](DOCKER.md)**: Comprehensive Docker setup and deployment guide
- **[API Documentation](docs/)**: Detailed API reference and examples
- **[Architecture Guide](docs/)**: System architecture and design decisions

## 🚀 Production Deployment

### AWS ECS Fargate
The application is designed for AWS ECS Fargate deployment:

1. **Docker Image**: Uses official TeXLive base image (~4GB)
2. **Resource Requirements**: 2GB RAM, 1 CPU recommended
3. **Environment Variables**: All configuration via environment variables
4. **Health Checks**: Built-in health monitoring

See [DOCKER.md](DOCKER.md) for detailed deployment instructions.

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with Docker
./scripts/docker-dev.sh test

# Test specific functionality
poetry run python test_asset_conversion.py
```

## 📊 API Endpoints

- `GET /api/v1/health` - Service health check
- `POST /api/v1/convert` - Convert LaTeX to HTML5
- `GET /api/v1/convert/{id}` - Check conversion status
- `GET /api/v1/convert/{id}/download` - Download results

## 🛠️ Configuration

All settings can be configured via environment variables:

- **Tool Paths**: TECTONIC_PATH, LATEXML_PATH, DVISVGM_PATH
- **File Limits**: MAX_FILE_SIZE, CONVERSION_TIMEOUT
- **Server Settings**: HOST, PORT, DEBUG
- **Security**: SECRET_KEY, ALLOWED_ORIGINS

See `docker.env.template` for all available options.

## 📈 Performance

- **Concurrent Processing**: Multiple conversions in parallel
- **Resource Management**: Configurable memory and CPU limits
- **Background Jobs**: Non-blocking conversion processing
- **Asset Optimization**: SVG optimization for smaller file sizes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For issues and questions:
- Check the [DOCKER.md](DOCKER.md) troubleshooting section
- Review the API documentation
- Open an issue on GitHub
