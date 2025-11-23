# Production Deployment Guide

This guide covers deploying the MCP Snapshot Server in production environments.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
- [Monitoring](#monitoring)
- [Security](#security)
- [Maintenance](#maintenance)

## Prerequisites

### System Requirements
- **Python**: 3.10 or higher
- **Memory**: Minimum 2GB RAM (4GB+ recommended for large transcripts)
- **Disk Space**: 1GB for dependencies + storage for generated snapshots
- **OS**: Linux (Ubuntu 20.04+), macOS 11+, or Windows 10+

### Required Software
```bash
# uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Git (for cloning)
# System-specific: apt-get install git / brew install git / etc.
```

### API Keys
- Anthropic API key with Claude access
- Sufficient API credits for snapshot generation

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/your-org/mcp-snapshot-server.git
cd mcp-snapshot-server
```

### 2. Install Dependencies
```bash
# Install all dependencies including dev tools
uv sync --all-extras

# For production (minimal install)
uv sync
```

### 3. Download NLP Models
```bash
# Download spaCy model
uv run python -m spacy download en_core_web_sm

# Download NLTK data
uv run python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```

### 4. Verify Installation
```bash
# Run tests
uv run pytest tests/ -v

# Check server can start
uv run mcp-snapshot-server --help
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required
LLM_ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Optional - LLM Settings
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=4000
LLM_MAX_TOKENS_PER_SECTION=2000

# Optional - Workflow Settings
WORKFLOW_PARALLEL_SECTION_GENERATION=false
WORKFLOW_MIN_CONFIDENCE_THRESHOLD=0.5
WORKFLOW_MAX_IMPROVEMENT_ITERATIONS=2

# Optional - NLP Settings
NLP_SPACY_MODEL=en_core_web_sm
NLP_MAX_ENTITIES_PER_TYPE=10
NLP_MAX_TOPICS=15

# Optional - MCP Settings
MCP_SERVER_NAME=mcp-snapshot-server
MCP_SERVER_VERSION=1.0.0

# Optional - Logging
LOG_LEVEL=INFO
```

### Configuration File (Alternative)

Create `config.yaml`:
```yaml
llm:
  anthropic_api_key: ${ANTHROPIC_API_KEY}
  model: claude-3-5-sonnet-20241022
  temperature: 0.3

workflow:
  parallel_section_generation: false
  min_confidence_threshold: 0.5

nlp:
  spacy_model: en_core_web_sm
  max_entities_per_type: 10
```

## Deployment Options

### Option 1: Claude Desktop Integration (Recommended)

See [CLAUDE_DESKTOP.md](CLAUDE_DESKTOP.md) for detailed instructions.

**Quick Setup:**
1. Find your uv path: `which uv`
2. Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mcp-snapshot-server": {
      "command": "/Users/yourname/.local/bin/uv",
      "args": [
        "--directory",
        "/path/to/mcp-snapshot-server",
        "run",
        "mcp-snapshot-server"
      ],
      "env": {
        "LLM_ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

**Important:** Use the full path to `uv` (not just "uv") - Claude Desktop doesn't inherit your terminal's PATH.

3. Restart Claude Desktop

### Option 2: Standalone Server

For API access or custom integrations:

```bash
# Run server directly
uv run mcp-snapshot-server

# Or with custom config
LLM_API_KEY=your-key uv run mcp-snapshot-server
```

### Option 3: Docker Deployment

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Download models
RUN uv run python -m spacy download en_core_web_sm
RUN uv run python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Run server
CMD ["uv", "run", "mcp-snapshot-server"]
```

**Build and run:**
```bash
docker build -t mcp-snapshot-server .
docker run -e LLM_ANTHROPIC_API_KEY=your-key mcp-snapshot-server
```

### Option 4: systemd Service (Linux)

Create `/etc/systemd/system/mcp-snapshot-server.service`:
```ini
[Unit]
Description=MCP Snapshot Server
After=network.target

[Service]
Type=simple
User=mcp-user
WorkingDirectory=/opt/mcp-snapshot-server
Environment="LLM_ANTHROPIC_API_KEY=your-api-key"
ExecStart=/home/mcp-user/.local/bin/uv run mcp-snapshot-server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-snapshot-server
sudo systemctl start mcp-snapshot-server
sudo systemctl status mcp-snapshot-server
```

## Monitoring

### Health Checks

The server logs structured JSON to stderr. Monitor for:

```bash
# View logs
journalctl -u mcp-snapshot-server -f

# Or with Docker
docker logs -f mcp-snapshot-server
```

### Key Metrics to Monitor

1. **Snapshot Generation Success Rate**
   - Monitor log entries with "Snapshot generated successfully"
   - Track average confidence scores

2. **API Usage**
   - LLM API call counts
   - Token usage
   - Error rates

3. **Performance**
   - Snapshot generation time
   - Memory usage
   - Queue depth (if implementing queuing)

### Example Monitoring Script

```python
import json
import sys

# Parse structured logs
for line in sys.stdin:
    try:
        log = json.loads(line)
        if log.get('level') == 'ERROR':
            # Alert on errors
            print(f"ERROR: {log.get('message')}")
        elif 'avg_confidence' in log:
            # Track confidence metrics
            print(f"Confidence: {log['avg_confidence']}")
    except json.JSONDecodeError:
        pass
```

## Security

See [SECURITY.md](SECURITY.md) for comprehensive security guidelines.

**Quick Checklist:**
- ✅ API keys stored in environment variables, not code
- ✅ File paths validated before processing
- ✅ Input validation on all VTT files
- ✅ Rate limiting configured
- ✅ Logs don't contain sensitive data
- ✅ Regular security updates

## Maintenance

### Regular Tasks

**Daily:**
- Monitor error logs
- Check API credit usage
- Verify snapshot generation success rate

**Weekly:**
- Review generated snapshots for quality
- Check disk space usage
- Update dependencies if needed

**Monthly:**
- Security updates
- Performance optimization review
- Backup configuration

### Updating the Server

```bash
# Pull latest changes
git pull origin main

# Update dependencies
uv sync

# Run tests
uv run pytest tests/

# Restart service
sudo systemctl restart mcp-snapshot-server
```

### Backup Strategy

**What to Back Up:**
1. Configuration files (.env, config.yaml)
2. Generated snapshots (if persisting to disk)
3. Custom prompts or field definitions
4. Logs (for audit trail)

**Example Backup Script:**
```bash
#!/bin/bash
BACKUP_DIR="/backup/mcp-snapshot-$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup configuration
cp .env $BACKUP_DIR/
cp config.yaml $BACKUP_DIR/ 2>/dev/null || true

# Backup snapshots
cp -r snapshots/ $BACKUP_DIR/ 2>/dev/null || true

# Compress
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup complete: $BACKUP_DIR.tar.gz"
```

### Troubleshooting

**Claude Desktop: "spawn uv ENOENT" Error:**

This is the most common error when setting up with Claude Desktop.

**Cause:** Claude Desktop cannot find the `uv` command because GUI apps don't inherit your terminal's PATH.

**Solution:**
```bash
# 1. Find your uv installation path
which uv
# Example output: /Users/yourname/.local/bin/uv

# 2. Update claude_desktop_config.json with the FULL path:
{
  "mcpServers": {
    "mcp-snapshot-server": {
      "command": "/Users/yourname/.local/bin/uv",  ← Use full path
      ...
    }
  }
}

# 3. Restart Claude Desktop completely (Cmd+Q then reopen)
```

Common uv locations:
- `~/.local/bin/uv` (standard installation)
- `/opt/homebrew/bin/uv` (Homebrew on Apple Silicon)
- `/usr/local/bin/uv` (Homebrew on Intel Mac)

**Server Won't Start:**
```bash
# Check Python version
python --version  # Should be 3.10+

# Verify dependencies
uv sync

# Check API key
echo $LLM_ANTHROPIC_API_KEY

# Test server manually
uv run python -m mcp_snapshot_server
```

**High Memory Usage:**
- Reduce `LLM_MAX_TOKENS`
- Disable parallel section generation
- Process smaller transcripts
- Add memory limits to Docker/systemd

**API Rate Limits:**
- Increase `RETRY_DELAY` in retry decorator
- Implement request queuing
- Contact Anthropic for rate limit increase

**Poor Quality Snapshots:**
- Check transcript quality (clear speaker labels, good content)
- Adjust `LLM_TEMPERATURE` (lower = more conservative)
- Review and customize section prompts
- Increase `LLM_MAX_TOKENS_PER_SECTION`

## Performance Optimization

### For Large Transcripts

```python
# config.yaml
workflow:
  # Process sections in parallel (faster but more API calls)
  parallel_section_generation: true

llm:
  # Use faster model for initial analysis
  model: claude-3-haiku-20240307  # Faster, cheaper
  # Then use Sonnet for sections
```

### For High Volume

1. **Implement Request Queue**
   - Use Redis or RabbitMQ
   - Process snapshots asynchronously
   - Return job ID immediately

2. **Cache Results**
   - Cache transcript analysis
   - Reuse section generations when possible

3. **Batch Processing**
   - Process multiple transcripts in batches
   - Optimize API usage

### Scaling Horizontally

**Load Balancer Configuration:**
```nginx
upstream mcp_servers {
    server mcp-server-1:8000;
    server mcp-server-2:8000;
    server mcp-server-3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://mcp_servers;
    }
}
```

## Cost Optimization

### API Usage

- Use Claude Haiku for analysis (cheaper)
- Use Claude Sonnet for sections (balanced)
- Cache frequently accessed data
- Implement smart retry logic

### Monitoring Costs

```python
# Track token usage
def log_api_usage(response):
    tokens = response.get('usage', {})
    print(f"Input tokens: {tokens.get('input_tokens')}")
    print(f"Output tokens: {tokens.get('output_tokens')}")
    # Calculate cost based on model pricing
```

## Support

For production support:
1. Check logs first
2. Review this deployment guide
3. Check [TROUBLESHOOTING.md](README.md#troubleshooting)
4. Open GitHub issue with logs and configuration (remove secrets!)

## Appendix

### Complete Example: Production Setup

```bash
# 1. System setup (Ubuntu 20.04)
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv git

# 2. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 3. Clone and setup
git clone https://github.com/your-org/mcp-snapshot-server.git
cd mcp-snapshot-server
uv sync

# 4. Download models
uv run python -m spacy download en_core_web_sm

# 5. Configure
cat > .env << EOF
LLM_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
LLM_MODEL=claude-3-5-sonnet-20241022
LOG_LEVEL=INFO
EOF

# 6. Test
uv run pytest tests/ -v

# 7. Deploy as systemd service
sudo cp deploy/mcp-snapshot-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mcp-snapshot-server
sudo systemctl start mcp-snapshot-server

# 8. Verify
sudo systemctl status mcp-snapshot-server
journalctl -u mcp-snapshot-server -f
```

### Environment-Specific Configurations

**Development:**
```bash
LOG_LEVEL=DEBUG
LLM_TEMPERATURE=0.5
WORKFLOW_PARALLEL_SECTION_GENERATION=false
```

**Staging:**
```bash
LOG_LEVEL=INFO
LLM_MODEL=claude-3-haiku-20240307  # Cheaper for testing
WORKFLOW_MIN_CONFIDENCE_THRESHOLD=0.3
```

**Production:**
```bash
LOG_LEVEL=WARNING
LLM_MODEL=claude-3-5-sonnet-20241022
WORKFLOW_MIN_CONFIDENCE_THRESHOLD=0.5
WORKFLOW_PARALLEL_SECTION_GENERATION=true
```
