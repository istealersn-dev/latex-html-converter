# LaTeX to HTML5 Converter - Instructions

## Overview

This service converts LaTeX documents to HTML5 with support for complex academic papers including RSTA and GEO formats. It features automatic package detection, custom document class support, and graceful fallback mechanisms.

## Quick Start

### 1. Build and Start the Service

```bash
# Build the Docker image
docker-compose build --no-cache

# Start the service
docker-compose up -d

# Check service health
curl -f http://localhost:8000/api/v1/health
```

### 2. Convert a LaTeX Document

```bash
# Convert a ZIP file containing LaTeX documents
curl -X POST \
  -F "file=@your-document.zip" \
  -F "options={\"latexml_options\":{\"output_format\":\"html\",\"include_mathml\":true,\"include_css\":true,\"include_javascript\":true}}" \
  http://localhost:8000/api/v1/convert
```

### 3. Check Conversion Status

```bash
# Replace {conversion_id} with the ID returned from the upload
curl -s "http://localhost:8000/api/v1/convert/{conversion_id}" | jq .
```

## Docker Commands

### Service Management

```bash
# Start the service
docker-compose up -d

# Stop the service
docker-compose down

# Restart the service
docker-compose restart

# View logs
docker-compose logs -f

# View recent logs
docker-compose logs --tail=50
```

### Container Access

```bash
# Access the running container
docker exec -it latex-html-converter bash

# Run commands in the container
docker exec latex-html-converter <command>
```

## Output Files Location

### Temporary Storage

Output files are stored in temporary directories within the Docker container:

```
/tmp/conversion_{uuid}_{random}/
├── output/
│   ├── final.html              # Final processed HTML
│   ├── latexml/
│   │   ├── {document}.html      # LaTeXML output
│   │   ├── LaTeXML.css         # LaTeXML stylesheet
│   │   └── ltx-article.css     # Article stylesheet
│   └── tectonic/               # Tectonic output (if used)
```

### Retrieving Output Files

#### Method 1: Copy from Container

```bash
# Find the conversion directory
docker exec latex-html-converter find /tmp -name "*conversion*" -type d

# Copy the final HTML file
docker cp latex-html-converter:/tmp/conversion_xxx/output/final.html ./output.html

# Copy the entire output directory
docker cp latex-html-converter:/tmp/conversion_xxx/output/ ./conversion_output/
```

#### Method 2: Access via Container Shell

```bash
# Access the container
docker exec -it latex-html-converter bash

# Navigate to the output directory
cd /tmp/conversion_xxx/output/

# View the files
ls -la

# View the HTML content
cat final.html
```

#### Method 3: Mount Persistent Volume (Recommended for Production)

Add to `docker-compose.yml`:

```yaml
services:
  latex-converter:
    volumes:
      - ./outputs:/app/outputs
      - ./uploads:/app/uploads
```

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### System Diagnostics

```bash
curl http://localhost:8000/api/v1/debug/system
```

### Conversion Endpoints

```bash
# Start conversion
POST /api/v1/convert

# Check conversion status
GET /api/v1/convert/{conversion_id}

# List active conversions
GET /api/v1/debug/conversions

# Get conversion logs
GET /api/v1/debug/conversion/{conversion_id}/logs
```

## Supported Document Types

### Academic Papers
- **RSTA**: Royal Society Transactions A papers
- **GEO**: Geophysics journal papers
- **Standard LaTeX**: Article, report, book classes

### Features
- ✅ Custom document classes (rstransa.cls, geophysics.cls)
- ✅ Automatic package detection and installation
- ✅ Graphics and bibliography support
- ✅ MathML rendering with MathJax
- ✅ Graceful fallback when Tectonic fails
- ✅ Project structure preservation

## Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check Docker is running
docker --version

# Check port availability
netstat -an | grep 8000

# Rebuild the image
docker-compose build --no-cache
```

#### 2. Conversion Fails
```bash
# Check service logs
docker-compose logs --tail=100

# Check system diagnostics
curl http://localhost:8000/api/v1/debug/system
```

#### 3. Output Files Not Found
```bash
# List all conversion directories
docker exec latex-html-converter find /tmp -name "*conversion*" -type d

# Check the most recent conversion
docker exec latex-html-converter ls -la /tmp/conversion_*/output/
```

### Debug Commands

```bash
# Check LaTeXML installation
docker exec latex-html-converter latexmlc --version

# Check Tectonic installation
docker exec latex-html-converter tectonic --version

# Check available LaTeX packages
docker exec latex-html-converter tlmgr list --only-installed | head -20
```

## Configuration

### Environment Variables

```bash
# Development mode
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Tool paths (Docker TeXLive paths)
TECTONIC_PATH=/usr/local/bin/tectonic
LATEXML_LATEXML_PATH=/usr/bin/latexmlc
DVISVGM_PATH=/usr/bin/dvisvgm
```

### LaTeXML Options

```json
{
  "latexml_options": {
    "output_format": "html",
    "include_mathml": true,
    "include_css": true,
    "include_javascript": true,
    "strict_mode": false,
    "verbose": false
  }
}
```

## Performance

### Resource Usage
- **Memory**: ~8GB for full TeXLive installation
- **CPU**: Variable based on document complexity
- **Storage**: Temporary files in `/tmp` (cleaned up automatically)

### Conversion Times
- **Simple documents**: 5-10 seconds
- **Complex academic papers**: 15-30 seconds
- **With fallback**: 20-40 seconds

## Security

### File Validation
- ZIP files are validated for safety
- LaTeX files are checked for malicious patterns
- Shell commands are sanitized

### Container Security
- Non-root user execution
- Restricted file system access
- Limited network access

## Production Deployment

### Recommended Setup

1. **Persistent Storage**: Mount output directories
2. **Resource Limits**: Set memory and CPU limits
3. **Logging**: Configure log rotation
4. **Monitoring**: Set up health checks
5. **Backup**: Regular backup of output files

### Docker Compose Production Example

```yaml
version: '3.8'
services:
  latex-converter:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./outputs:/app/outputs
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      - LOG_LEVEL=INFO
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
```

## Support

For issues or questions:
1. Check the logs: `docker-compose logs`
2. Verify system status: `curl http://localhost:8000/api/v1/health`
3. Check diagnostics: `curl http://localhost:8000/api/v1/debug/system`

## License

This project is part of the LaTeX to HTML5 Converter system.
