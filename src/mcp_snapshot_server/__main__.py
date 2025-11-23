"""Main entry point for MCP Snapshot Server.

Run with: python -m mcp_snapshot_server
or: uv run mcp-snapshot-server
"""

import asyncio

from mcp_snapshot_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
