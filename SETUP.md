# Setup Guide - MCP Snapshot Server

This guide provides detailed instructions for setting up your development environment and getting the MCP Snapshot Server running.

## Prerequisites

### Required Software

1. **Python 3.10 or higher**
   ```bash
   python --version  # Should show 3.10.x or higher
   ```

2. **uv Package Manager**
   ```bash
   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Verify installation
   uv --version
   ```

3. **Anthropic API Key**
   - Sign up at https://console.anthropic.com
   - Create an API key from your dashboard
   - Keep it secure - never commit it to version control

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/arthurfantaci/mcp-snapshot-server.git
cd mcp-snapshot-server
```

### 2. Install Dependencies

```bash
# Install all dependencies (including dev dependencies)
uv sync --all-extras

# This creates a virtual environment in .venv and installs:
# - Core dependencies (mcp, anthropic, pydantic, etc.)
# - Dev dependencies (ruff, mypy, pytest, etc.)
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your preferred editor
nano .env  # or vim, code, etc.
```

**Required Configuration:**
```bash
# At minimum, set your Anthropic API key
LLM_ANTHROPIC_API_KEY=sk-ant-your-actual-api-key-here
```

**Optional Configuration:**
Adjust other settings as needed (see `.env.example` for all options)

### 4. Verify Installation

```bash
# Run code quality checks
uv run ruff format --check .
uv run ruff check .
uv run mypy src/mcp_snapshot_server/

# Run tests (once Phase 1 tests are written)
uv run pytest
```

## Development Workflow

### Running the Server

```bash
# Start the MCP server
uv run mcp-snapshot-server
```

### Code Quality Commands

```bash
# Format code (run before committing)
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Auto-fix linting issues where possible
uv run ruff check --fix .

# Type checking
uv run mypy src/mcp_snapshot_server/

# Run all quality checks
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test types
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only

# Run with coverage report
uv run pytest --cov=mcp_snapshot_server --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Working with Dependencies

```bash
# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Update all dependencies
uv sync

# Update lock file
uv lock
```

## Claude Desktop Integration

### macOS Configuration

1. **Locate Claude Desktop config file:**
   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. **Add server configuration:**
   ```json
   {
     "mcpServers": {
       "snapshot-server": {
         "command": "uv",
         "args": [
           "run",
           "mcp-snapshot-server"
         ],
         "cwd": "/absolute/path/to/mcp-snapshot-server",
         "env": {
           "LLM_ANTHROPIC_API_KEY": "your_api_key_here"
         }
       }
     }
   }
   ```

3. **Restart Claude Desktop**

### Windows Configuration

1. **Config file location:**
   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. **Use Windows path format:**
   ```json
   {
     "mcpServers": {
       "snapshot-server": {
         "command": "uv",
         "args": ["run", "mcp-snapshot-server"],
         "cwd": "C:\\path\\to\\mcp-snapshot-server",
         "env": {
           "LLM_ANTHROPIC_API_KEY": "your_api_key_here"
         }
       }
     }
   }
   ```

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem:** `ModuleNotFoundError: No module named 'mcp_snapshot_server'`

**Solution:**
```bash
# Ensure you're in the project root directory
cd /path/to/mcp-snapshot-server

# Reinstall dependencies
uv sync --all-extras

# Verify the package is installed
uv pip list | grep mcp-snapshot-server
```

#### 2. API Key Not Found

**Problem:** `ValueError: ANTHROPIC_API_KEY is required`

**Solution:**
```bash
# Check .env file exists
ls -la .env

# Verify API key is set
grep LLM_ANTHROPIC_API_KEY .env

# Ensure no extra spaces or quotes
# Correct format:
LLM_ANTHROPIC_API_KEY=sk-ant-your-key-here
```

#### 3. Permission Errors

**Problem:** Permission denied when running commands

**Solution:**
```bash
# Ensure uv is in your PATH
echo $PATH | grep uv

# Reinstall uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your terminal
```

#### 4. spaCy Model Not Found

**Problem:** `OSError: Can't find model 'en_core_web_sm'`

**Solution:**
```bash
# The spaCy model will be downloaded when first needed
# Or manually download:
uv run python -c "import spacy; spacy.cli.download('en_core_web_sm')"
```

## IDE Setup

### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Ruff
- Even Better TOML

Recommended settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": false,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  }
}
```

### PyCharm

1. **Set Python Interpreter:**
   - File → Settings → Project → Python Interpreter
   - Select `.venv/bin/python`

2. **Configure Tools:**
   - File → Settings → Tools → External Tools
   - Add Ruff for formatting and linting

## Next Steps

1. Read the [project specification](MCP_Server_Project_Specification.md) for architectural details
2. Review the [README.md](README.md) for usage examples
3. Explore the codebase structure in `src/mcp_snapshot_server/`
4. Run the example tests in `tests/`
5. Start contributing!

## Getting Help

- Check the [GitHub Issues](https://github.com/arthurfantaci/mcp-snapshot-server/issues)
- Review the [MCP Documentation](https://modelcontextprotocol.io/docs)
- Consult the [Anthropic API Docs](https://docs.anthropic.com)

## Development Best Practices

1. **Always run code quality checks before committing:**
   ```bash
   uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
   ```

2. **Write tests for new functionality:**
   ```bash
   # Tests should go in tests/ directory matching the source structure
   ```

3. **Keep dependencies up to date:**
   ```bash
   uv sync
   ```

4. **Use type hints:**
   ```python
   def my_function(param: str) -> dict[str, Any]:
       ...
   ```

5. **Follow the commit message convention:**
   ```
   feat: Add new section generator
   fix: Resolve VTT parsing error
   docs: Update SETUP.md
   test: Add tests for Analysis Agent
   ```
