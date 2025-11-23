"""Main entry point for MCP Snapshot Server.

Run with: python -m mcp_snapshot_server
or: uv run mcp-snapshot-server
"""

from mcp_snapshot_server.server import main

if __name__ == "__main__":
    main()
