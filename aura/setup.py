"""
aura.setup — Auto-configure AI tools to connect to aura's MCP server.

Detects which tools are installed and writes their config files
so they automatically read your context packs via MCP.

Supported tools:
  - Claude Desktop (macOS + Windows + Linux)
  - Claude Code CLI
  - ChatGPT Desktop (macOS + Windows)
  - Cursor IDE
  - Windsurf IDE
  - VS Code (with Copilot MCP)
  - Gemini CLI
  - Codex CLI
"""

from __future__ import annotations

import json
import platform
import shutil
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
    return None


def _get_cursor_config_path() -> Optional[Path]:
    """Get Cursor MCP config path."""
    return Path.home() / ".cursor" / "mcp.json"


def _get_windsurf_config_path() -> Optional[Path]:
    """Get Windsurf MCP config path."""
    return Path.home() / ".windsurf" / "mcp.json"


def _get_vscode_config_path() -> Optional[Path]:
    """Get VS Code MCP config path (for Copilot MCP support)."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Code" / "User" / "settings.json"
    return None


def _get_claude_code_config_path() -> Optional[Path]:
    """Get Claude Code MCP config path."""
    return Path.home() / ".claude" / "mcp.json"


def _get_gemini_config_path() -> Optional[Path]:
    """Get Gemini CLI settings path."""
    return Path.home() / ".gemini" / "settings.json"


def _get_codex_config_path() -> Optional[Path]:
    """Get Codex CLI MCP config path."""
    return Path.home() / ".codex" / "mcp.json"


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
# Generic JSON config writer
# ---------------------------------------------------------------------------
def _setup_json_mcp_tool(
    tool_name: str,
    config_path: Optional[Path],
    mcp_config: dict,
    host: str = "localhost",
    port: int = 3847,
    servers_key: str = "mcpServers",
) -> dict:
    """Generic setup for tools that store MCP config as JSON with mcpServers."""
    if config_path is None:
        return {"success": False, "path": None, "action": "skip",
                "message": f"No config path found for {tool_name}"}

    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    else:
        config = {}

    mcp_servers = config.get(servers_key, {})
    if "aura" in mcp_servers:
        return {
            "success": True,
            "path": str(config_path),
            "action": "already_configured",
            "message": f"aura is already configured in {tool_name}",
        }

    mcp_servers["aura"] = mcp_config
    config[servers_key] = mcp_servers

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "path": str(config_path),
        "action": "configured",
        "message": f"Added aura MCP server to {tool_name} config",
    }


# ---------------------------------------------------------------------------
# Tool configurators
# ---------------------------------------------------------------------------
def setup_claude_desktop(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Claude Desktop to connect to aura MCP server."""
    return _setup_json_mcp_tool(
        "Claude Desktop", _get_claude_config_path(),
        _aura_mcp_config(host, port), host, port,
    )


def setup_cursor(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Cursor IDE to connect to aura MCP server."""
    return _setup_json_mcp_tool(
        "Cursor", _get_cursor_config_path(),
        _aura_mcp_config(host, port), host, port,
    )


def setup_windsurf(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Windsurf IDE to connect to aura MCP server."""
    return _setup_json_mcp_tool(
        "Windsurf", _get_windsurf_config_path(),
        _aura_mcp_config(host, port), host, port,
    )


def setup_vscode(host: str = "localhost", port: int = 3847) -> dict:
    """Configure VS Code (Copilot MCP) to connect to aura MCP server."""
    config_path = _get_vscode_config_path()
    if config_path is None:
        return {"success": False, "path": None, "action": "skip",
                "message": "No VS Code config path found"}

    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    else:
        config = {}

    # VS Code uses "mcp" → "servers" structure for Copilot MCP
    mcp = config.get("mcp", {})
    servers = mcp.get("servers", {})

    if "aura" in servers:
        return {
            "success": True,
            "path": str(config_path),
            "action": "already_configured",
            "message": "aura is already configured in VS Code",
        }

    servers["aura"] = {
        "type": "http",
        "url": f"http://{host}:{port}/mcp",
    }
    mcp["servers"] = servers
    config["mcp"] = mcp

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "path": str(config_path),
        "action": "configured",
        "message": "Added aura MCP server to VS Code (Copilot MCP)",
    }


def setup_claude_code(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Claude Code CLI to connect to aura MCP server."""
    return _setup_json_mcp_tool(
        "Claude Code", _get_claude_code_config_path(),
        _aura_mcp_config(host, port), host, port,
    )


def setup_gemini(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Gemini CLI to connect to aura MCP server."""
    config_path = _get_gemini_config_path()
    if config_path is None:
        return {"success": False, "path": None, "action": "skip",
                "message": "No Gemini CLI config path found"}

    return _setup_json_mcp_tool(
        "Gemini CLI", config_path,
        {"url": f"http://{host}:{port}/sse"}, host, port,
    )


def setup_codex(host: str = "localhost", port: int = 3847) -> dict:
    """Configure Codex CLI to connect to aura MCP server."""
    return _setup_json_mcp_tool(
        "Codex", _get_codex_config_path(),
        _aura_mcp_config(host, port), host, port,
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
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
            "setup_fn": "setup_claude_desktop",
        })

    # Claude Code CLI
    claude_code_installed = shutil.which("claude") is not None
    claude_code_path = _get_claude_code_config_path()
    tools.append({
        "name": "Claude Code",
        "installed": claude_code_installed,
        "config_path": str(claude_code_path) if claude_code_path else None,
        "config_exists": claude_code_path.exists() if claude_code_path else False,
        "setup_fn": "setup_claude_code",
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
            "setup_fn": "setup_cursor",
        })

    # Windsurf
    windsurf_path = _get_windsurf_config_path()
    if windsurf_path:
        windsurf_installed = False
        if system == "Darwin":
            windsurf_installed = Path("/Applications/Windsurf.app").exists()
        else:
            windsurf_installed = windsurf_path.parent.exists()
        tools.append({
            "name": "Windsurf",
            "installed": windsurf_installed,
            "config_path": str(windsurf_path),
            "config_exists": windsurf_path.exists(),
            "setup_fn": "setup_windsurf",
        })

    # VS Code
    vscode_path = _get_vscode_config_path()
    if vscode_path:
        vscode_installed = False
        if system == "Darwin":
            vscode_installed = Path("/Applications/Visual Studio Code.app").exists()
        else:
            vscode_installed = shutil.which("code") is not None
        tools.append({
            "name": "VS Code",
            "installed": vscode_installed,
            "config_path": str(vscode_path),
            "config_exists": vscode_path.exists(),
            "setup_fn": "setup_vscode",
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
        "config_path": None,
        "config_exists": False,
        "manual_setup": True,
        "setup_fn": None,
    })

    # Gemini CLI
    gemini_installed = shutil.which("gemini") is not None
    gemini_path = _get_gemini_config_path()
    tools.append({
        "name": "Gemini CLI",
        "installed": gemini_installed,
        "config_path": str(gemini_path) if gemini_path else None,
        "config_exists": gemini_path.exists() if gemini_path else False,
        "setup_fn": "setup_gemini",
    })

    # Codex CLI
    codex_installed = shutil.which("codex") is not None
    codex_path = _get_codex_config_path()
    tools.append({
        "name": "Codex",
        "installed": codex_installed,
        "config_path": str(codex_path) if codex_path else None,
        "config_exists": codex_path.exists() if codex_path else False,
        "setup_fn": "setup_codex",
    })

    return tools
