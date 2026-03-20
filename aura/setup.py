"""
aura.setup — Auto-configure AI tools to connect to aura's MCP server.

Detects which tools are installed and writes their config files
so they automatically read your context packs via MCP.

Supported tools:
  - Claude Desktop (macOS + Windows + Linux)
  - ChatGPT Desktop (macOS + Windows)
  - Cursor IDE
  - Gemini CLI
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Config file locations per tool and OS
# ---------------------------------------------------------------------------
def _get_claude_config_path() -> Optional[Path]:
    """Get Claude Desktop config path for current OS."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return None


def _get_chatgpt_config_path() -> Optional[Path]:
    """Get ChatGPT Desktop config path (Developer Mode MCP)."""
    # ChatGPT Desktop uses Developer Mode for MCP — no local config file.
    # We return a sentinel path to indicate it's available but needs manual setup.
    return None


def _get_cursor_config_path() -> Optional[Path]:
    """Get Cursor MCP config path."""
    return Path.home() / ".cursor" / "mcp.json"


def _get_gemini_config_path() -> Optional[Path]:
    """Get Gemini CLI settings path."""
    return Path.home() / ".gemini" / "settings.json"


# ---------------------------------------------------------------------------
# MCP server config block
# ---------------------------------------------------------------------------
def _aura_mcp_config(host: str = "localhost", port: int = 3847) -> dict:
    """Return the aura MCP server config block."""
    return {
        "url": f"http://{host}:{port}/mcp"
    }


def _aura_mcp_config_sse(host: str = "localhost", port: int = 3847) -> dict:
    """Return the aura MCP server config block (SSE endpoint)."""
    return {
        "url": f"http://{host}:{port}/sse"
    }


# ---------------------------------------------------------------------------
# Tool configurators
# ---------------------------------------------------------------------------
def setup_claude_desktop(host: str = "localhost", port: int = 3847) -> dict:
    """
    Configure Claude Desktop to connect to aura MCP server.

    Returns:
        dict with keys: success, path, action, message
    """
    config_path = _get_claude_config_path()
    if config_path is None:
        return {"success": False, "path": None, "action": "skip", "message": "Unsupported OS"}

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    else:
        config = {}

    # Check if aura is already configured
    mcp_servers = config.get("mcpServers", {})
    if "aura" in mcp_servers:
        return {
            "success": True,
            "path": str(config_path),
            "action": "already_configured",
            "message": "aura is already configured in Claude Desktop",
        }

    # Add aura
    mcp_servers["aura"] = _aura_mcp_config(host, port)
    config["mcpServers"] = mcp_servers

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "path": str(config_path),
        "action": "configured",
        "message": "Added aura MCP server to Claude Desktop config",
    }


def setup_cursor(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Cursor IDE to connect to aura MCP server."""
    config_path = _get_cursor_config_path()
    if config_path is None:
        return {"success": False, "path": None, "action": "skip", "message": "Unsupported OS"}

    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    else:
        config = {}

    mcp_servers = config.get("mcpServers", {})
    if "aura" in mcp_servers:
        return {
            "success": True,
            "path": str(config_path),
            "action": "already_configured",
            "message": "aura is already configured in Cursor",
        }

    mcp_servers["aura"] = _aura_mcp_config(host, port)
    config["mcpServers"] = mcp_servers

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "path": str(config_path),
        "action": "configured",
        "message": "Added aura MCP server to Cursor config",
    }


def setup_gemini(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Gemini CLI to connect to aura MCP server."""
    config_path = _get_gemini_config_path()
    if config_path is None:
        return {"success": False, "path": None, "action": "skip", "message": "Unsupported OS"}

    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    else:
        config = {}

    mcp_servers = config.get("mcpServers", {})
    if "aura" in mcp_servers:
        return {
            "success": True,
            "path": str(config_path),
            "action": "already_configured",
            "message": "aura is already configured in Gemini CLI",
        }

    # Gemini CLI uses SSE transport
    mcp_servers["aura"] = {
        "url": f"http://{host}:{port}/sse"
    }
    config["mcpServers"] = mcp_servers

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "path": str(config_path),
        "action": "configured",
        "message": "Added aura MCP server to Gemini CLI config",
    }


def detect_installed_tools() -> list[dict]:
    """Detect which AI tools are installed on this machine."""
    tools = []
    system = platform.system()

    # Claude Desktop
    claude_path = _get_claude_config_path()
    if claude_path:
        claude_installed = False
        if system == "Darwin":
            claude_installed = Path("/Applications/Claude.app").exists()
        else:
            claude_installed = claude_path.parent.exists()
        tools.append({
            "name": "Claude Desktop",
            "installed": claude_installed,
            "config_path": str(claude_path),
            "config_exists": claude_path.exists(),
        })

    # Cursor
    cursor_path = _get_cursor_config_path()
    if cursor_path:
        cursor_installed = False
        if system == "Darwin":
            cursor_installed = Path("/Applications/Cursor.app").exists()
        else:
            cursor_installed = cursor_path.parent.exists()
        tools.append({
            "name": "Cursor",
            "installed": cursor_installed,
            "config_path": str(cursor_path),
            "config_exists": cursor_path.exists(),
        })

    # ChatGPT Desktop
    if system == "Darwin":
        chatgpt_installed = Path("/Applications/ChatGPT.app").exists()
    elif system == "Windows":
        chatgpt_installed = (Path.home() / "AppData" / "Local" / "Programs" / "ChatGPT").exists()
    else:
        chatgpt_installed = False

    tools.append({
        "name": "ChatGPT Desktop",
        "installed": chatgpt_installed,
        "config_path": None,  # Uses Developer Mode, no local config
        "config_exists": False,
        "manual_setup": True,
    })

    # Gemini CLI
    import shutil
    gemini_installed = shutil.which("gemini") is not None
    gemini_path = _get_gemini_config_path()
    tools.append({
        "name": "Gemini CLI",
        "installed": gemini_installed,
        "config_path": str(gemini_path) if gemini_path else None,
        "config_exists": gemini_path.exists() if gemini_path else False,
    })

    return tools
