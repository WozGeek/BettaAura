"""
aura.mcp_server — Model Context Protocol Server

Serves your context packs to any MCP-compatible AI client.
Run with: aura serve

Security:
  - Binds to localhost only (127.0.0.1) by default
  - Optional token authentication via --token flag
  - Scoped serving via --packs flag (only serve specific packs)

Exposes context packs as:
  - Resources: each pack is a readable resource
  - Tools: query, search, and mutate packs programmatically
  - Prompts: pre-built prompt templates that include your context

Protocol spec: https://modelcontextprotocol.io/specification/2025-11-25
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from aura import __version__
from aura.exporters.system_prompt import export_system_prompt
from aura.pack import (
    get_packs_dir,
    init_aura,
    list_packs,
    load_pack,
    pack_exists,
    save_pack,
)
from aura.schema import Confidence, Fact, Rule

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="aura MCP Server", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_aura()


# ---------------------------------------------------------------------------
# Security: token auth + scoped packs
# ---------------------------------------------------------------------------
_AUTH_TOKEN: str | None = os.environ.get("AURA_TOKEN", None)
_ALLOWED_PACKS: list[str] | None = None  # None = all packs
_WRITE_ENABLED: bool = True  # Can be disabled with --read-only


def configure_security(
    token: str | None = None,
    allowed_packs: list[str] | None = None,
    read_only: bool = False,
):
    """Configure server security settings. Called before server starts."""
    global _AUTH_TOKEN, _ALLOWED_PACKS, _WRITE_ENABLED
    if token:
        _AUTH_TOKEN = token
    if allowed_packs:
        _ALLOWED_PACKS = allowed_packs
    _WRITE_ENABLED = not read_only


def _check_auth(request: Request) -> bool:
    """Check if request is authenticated. Returns True if OK."""
    if _AUTH_TOKEN is None:
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header == f"Bearer {_AUTH_TOKEN}":
        return True
    # Also check query param for SSE clients that can't set headers
    if request.query_params.get("token") == _AUTH_TOKEN:
        return True
    return False


def _filter_packs(packs):
    """Filter packs based on allowed list."""
    if _ALLOWED_PACKS is None:
        return packs
    return [p for p in packs if p.name in _ALLOWED_PACKS]


def _is_pack_allowed(pack_name: str) -> bool:
    """Check if a specific pack is allowed to be served."""
    if _ALLOWED_PACKS is None:
        return True
    return pack_name in _ALLOWED_PACKS


def _compact_profile(packs: list, max_facts: int | None = None) -> str:
    """Generate a compact user profile from all packs. Optimized for token efficiency."""
    lines = []

    # Identity facts first (highest value per token)
    identity = []
    skills = []
    preferences = []
    rules = []

    for pack in packs:
        facts = pack.facts
        if max_facts:
            facts = sorted(
                facts,
                key=lambda f: (
                    0 if f.confidence == Confidence.HIGH else
                    1 if f.confidence == Confidence.MEDIUM else 2
                ),
            )[:max_facts]

        for fact in facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            val = _scrub_secrets(val)  # Redact before serving
            entry = f"{fact.key}: {val}"
            if fact.key.startswith("identity") or fact.key in ("role", "role.founder", "role.student", "role.employment"):
                identity.append(entry)
            elif fact.type in ("skill",) or fact.key in ("languages.primary", "frameworks", "editor", "ai_tools"):
                skills.append(entry)
            else:
                preferences.append(entry)

        for rule in pack.rules:
            rules.append(rule.instruction)

    if identity:
        lines.append("Identity: " + " | ".join(identity))
    if skills:
        lines.append("Stack: " + " | ".join(skills))
    if preferences:
        lines.append("Context: " + " | ".join(preferences[:10]))  # Cap at 10
    if rules:
        lines.append("Rules: " + " | ".join(rules[:5]))  # Cap at 5

    if not lines:
        return "No user context available."

    return "\n".join(lines)


def _scrub_secrets(text: str) -> str:
    """Scrub known secret patterns from text before serving to LLM."""
    try:
        from aura.audit import _COMPILED_PATTERNS, Severity
        for _, pattern, severity, _ in _COMPILED_PATTERNS:
            if severity == Severity.CRITICAL:
                text = pattern.sub("[REDACTED]", text)
    except ImportError:
        pass
    return text


def _identity_card(packs: list) -> str:
    """Generate an ultra-compact identity card. Target: ~50-100 tokens."""
    name = None
    role = None
    top_skills: list[str] = []
    top_rules: list[str] = []

    for pack in packs:
        for fact in pack.facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            val = _scrub_secrets(val)
            if fact.key == "identity.name" and not name:
                name = val
            elif fact.key in ("role", "role.employment", "role.founder") and not role:
                role = val
            elif fact.key in ("languages.primary", "frameworks", "editor") and len(top_skills) < 3:
                top_skills.append(f"{fact.key.split('.')[-1]}: {val}")
            elif fact.type and fact.type.value == "identity" and fact.key != "identity.name":
                if not role:
                    role = val

        for rule in pack.rules[:2]:  # Top 2 rules only
            if len(top_rules) < 2:
                top_rules.append(rule.instruction)

    parts = []
    if name:
        parts.append(name)
    if role:
        parts.append(role)
    header = " — ".join(parts) if parts else "User"

    lines = [header]
    if top_skills:
        lines.append("Stack: " + " | ".join(top_skills))
    if top_rules:
        lines.append("Key rules: " + " | ".join(top_rules))

    if len(lines) == 1 and lines[0] == "User":
        return "No user identity configured. Ask the user to run 'aura quickstart'."

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Protocol constants
# ---------------------------------------------------------------------------
SERVER_INFO = {"name": "aura", "version": __version__}

SERVER_CAPABILITIES = {
    "resources": {"listChanged": True},
    "tools": {},
    "prompts": {},
}

TOOLS = [
    {
        "name": "get_identity_card",
        "description": (
            "IMPORTANT: Call this tool AUTOMATICALLY at the start of EVERY conversation, "
            "before responding to the user's first message. Returns a ultra-compact identity "
            "card (~50-100 tokens): name, role, top 3 skills, and primary rules. "
            "This is the FASTEST way to know who you're talking to. "
            "For deeper context, follow up with get_context or get_user_profile."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_context",
        "description": (
            "Get the user's full context for a specific scope/domain. "
            "Returns structured facts and rules. Use this when you need detailed "
            "information about a particular area (e.g. their dev stack, writing style)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_name": {
                    "type": "string",
                    "description": "Name of the context pack (e.g. 'developer', 'writer', 'work')",
                },
            },
            "required": ["pack_name"],
        },
    },
    {
        "name": "get_all_context",
        "description": (
            "Get ALL context packs combined. This is a HEAVY call — use only when the user "
            "explicitly asks 'what do you know about me', 'who am I', or when you need "
            "comprehensive cross-domain context. Prefer get_identity_card for quick lookups "
            "and get_context for specific domains."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scopes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: filter to specific scopes. Empty = all.",
                },
                "max_facts": {
                    "type": "integer",
                    "description": "Max facts per pack (default: all). Use 10-20 for token efficiency.",
                },
                "compact": {
                    "type": "boolean",
                    "description": "If true, returns a compact summary instead of full export. Saves tokens.",
                },
            },
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Get a compact summary of the user — identity, stack, style, rules. "
            "Much shorter than get_all_context. Use this when you just need the basics. "
            "Typically under 500 tokens. Call this if you haven't loaded user context yet."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_context",
        "description": "Search through the user's context for specific information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'programming languages', 'writing style')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "add_fact",
        "description": (
            "Add a new fact to the user's context. Use when the user tells you "
            "something that should be remembered across sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_name": {"type": "string", "description": "Which pack to add to"},
                "key": {"type": "string", "description": "Fact key (e.g. 'languages.primary')"},
                "value": {"type": ["string", "array"], "description": "The fact value"},
                "fact_type": {
                    "type": "string",
                    "enum": ["preference", "identity", "skill", "style", "constraint", "context"],
                },
            },
            "required": ["pack_name", "key", "value"],
        },
    },
    {
        "name": "add_rule",
        "description": "Add a behavioral rule to a context pack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_name": {"type": "string"},
                "instruction": {"type": "string", "description": "The rule instruction"},
                "priority": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": ["pack_name", "instruction"],
        },
    },
    {
        "name": "list_packs",
        "description": "List all available context packs with metadata.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

PROMPTS = [
    {
        "name": "with_full_context",
        "description": "Include all of the user's context in the conversation",
        "arguments": [],
    },
    {
        "name": "with_scope",
        "description": "Include context for a specific scope only",
        "arguments": [
            {"name": "scope", "description": "The scope to include", "required": True}
        ],
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: dict) -> list[dict]:
    if name == "get_identity_card":
        packs = _filter_packs(list_packs())
        return [{"type": "text", "text": _identity_card(packs)}]

    elif name == "get_context":
        pack_name = arguments["pack_name"]
        if not _is_pack_allowed(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' is not available."}]
        if not pack_exists(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' not found. Use list_packs to see available packs."}]
        pack = load_pack(pack_name)
        return [{"type": "text", "text": pack.to_system_prompt()}]

    elif name == "get_all_context":
        packs = _filter_packs(list_packs())
        scopes = arguments.get("scopes", [])
        if scopes:
            packs = [p for p in packs if p.scope in scopes]
        if not packs:
            return [{"type": "text", "text": "No context packs found."}]

        max_facts = arguments.get("max_facts")
        compact = arguments.get("compact", False)

        if compact:
            return [{"type": "text", "text": _compact_profile(packs, max_facts)}]

        if max_facts:
            # Trim facts per pack — keep highest confidence first
            for pack in packs:
                sorted_facts = sorted(
                    pack.facts,
                    key=lambda f: (
                        0 if f.confidence == Confidence.HIGH else
                        1 if f.confidence == Confidence.MEDIUM else 2
                    ),
                )
                pack.facts = sorted_facts[:max_facts]

        return [{"type": "text", "text": export_system_prompt(packs, include_header=False)}]

    elif name == "get_user_profile":
        packs = _filter_packs(list_packs())
        return [{"type": "text", "text": _compact_profile(packs)}]

    elif name == "search_context":
        query = arguments["query"].lower()
        results = []
        for pack in _filter_packs(list_packs()):
            for fact in pack.facts:
                val_str = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                if query in fact.key.lower() or query in val_str.lower():
                    results.append(f"[{pack.name}/{pack.scope}] {fact.key}: {val_str}")
            for rule in pack.rules:
                if query in rule.instruction.lower():
                    results.append(f"[{pack.name}/{pack.scope}] Rule: {rule.instruction}")
        if not results:
            return [{"type": "text", "text": f"No context found matching '{arguments['query']}'."}]
        return [{"type": "text", "text": "\n".join(results)}]

    elif name == "add_fact":
        if not _WRITE_ENABLED:
            return [{"type": "text", "text": "Server is in read-only mode. Facts cannot be added."}]
        pack_name = arguments["pack_name"]
        if not _is_pack_allowed(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' is not available."}]
        if not pack_exists(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' not found."}]
        pack = load_pack(pack_name)
        existing = next((f for f in pack.facts if f.key == arguments["key"]), None)
        if existing:
            existing.value = arguments["value"]
            existing.updated_at = datetime.now()
            existing.source = "mcp"
        else:
            pack.facts.append(Fact(
                key=arguments["key"],
                value=arguments["value"],
                type=arguments.get("fact_type", "context"),
                confidence=Confidence.HIGH,
                source="mcp",
            ))
        save_pack(pack)
        return [{"type": "text", "text": f"✓ Added fact '{arguments['key']}' to '{pack_name}'."}]

    elif name == "add_rule":
        if not _WRITE_ENABLED:
            return [{"type": "text", "text": "Server is in read-only mode. Rules cannot be added."}]
        pack_name = arguments["pack_name"]
        if not _is_pack_allowed(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' is not available."}]
        if not pack_exists(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' not found."}]
        pack = load_pack(pack_name)
        pack.rules.append(Rule(
            instruction=arguments["instruction"],
            priority=arguments.get("priority", 5),
        ))
        save_pack(pack)
        return [{"type": "text", "text": f"✓ Added rule to '{pack_name}'."}]

    elif name == "list_packs":
        packs = _filter_packs(list_packs())
        if not packs:
            return [{"type": "text", "text": "No context packs found."}]
        lines = []
        for p in packs:
            lines.append(f"• {p.name} ({p.scope}) — {len(p.facts)} facts, {len(p.rules)} rules")
            if p.meta.description:
                lines.append(f"  {p.meta.description}")
        return [{"type": "text", "text": "\n".join(lines)}]

    return [{"type": "text", "text": f"Unknown tool: {name}"}]


# ---------------------------------------------------------------------------
# Resource handling
# ---------------------------------------------------------------------------
def get_resources() -> list[dict]:
    resources = []
    for pack in _filter_packs(list_packs()):
        resources.append({
            "uri": f"aura://packs/{pack.name}",
            "name": f"Context: {pack.name}",
            "description": pack.meta.description or f"{pack.scope} context pack",
            "mimeType": "text/plain",
        })
    resources.append({
        "uri": "aura://context/full",
        "name": "Full User Context",
        "description": "All context packs combined",
        "mimeType": "text/plain",
    })
    return resources


def read_resource(uri: str) -> list[dict]:
    if uri == "aura://context/full":
        packs = _filter_packs(list_packs())
        return [{"uri": uri, "mimeType": "text/plain", "text": export_system_prompt(packs)}]
    if uri.startswith("aura://packs/"):
        name = uri.replace("aura://packs/", "")
        if not _is_pack_allowed(name):
            return [{"uri": uri, "mimeType": "text/plain", "text": f"Pack not available: {name}"}]
        if pack_exists(name):
            pack = load_pack(name)
            return [{"uri": uri, "mimeType": "text/plain", "text": pack.to_system_prompt()}]
    return [{"uri": uri, "mimeType": "text/plain", "text": f"Resource not found: {uri}"}]


# ---------------------------------------------------------------------------
# Prompt execution
# ---------------------------------------------------------------------------
def get_prompt(name: str, arguments: dict) -> dict:
    if name == "with_full_context":
        packs = _filter_packs(list_packs())
        content = export_system_prompt(packs, include_header=False)
        return {
            "description": "Full user context",
            "messages": [{"role": "user", "content": {"type": "text", "text": f"Here is my personal context:\n\n{content}"}}],
        }
    elif name == "with_scope":
        scope = arguments.get("scope", "")
        packs = [p for p in _filter_packs(list_packs()) if p.scope == scope or p.name == scope]
        if not packs:
            return {"description": f"No context for '{scope}'", "messages": []}
        content = export_system_prompt(packs, include_header=False)
        return {
            "description": f"User context for {scope}",
            "messages": [{"role": "user", "content": {"type": "text", "text": f"Here is my {scope} context:\n\n{content}"}}],
        }
    return {"description": "Unknown prompt", "messages": []}


# ---------------------------------------------------------------------------
# JSON-RPC handler
# ---------------------------------------------------------------------------
def make_response(id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def handle_jsonrpc(data: dict) -> dict | None:
    method = data.get("method", "")
    rid = data.get("id")
    params = data.get("params", {})

    if method == "initialize":
        return make_response(rid, {
            "protocolVersion": "2025-11-25",
            "capabilities": SERVER_CAPABILITIES,
            "serverInfo": SERVER_INFO,
        })
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return make_response(rid, {})
    elif method == "resources/list":
        return make_response(rid, {"resources": get_resources()})
    elif method == "resources/read":
        return make_response(rid, {"contents": read_resource(params.get("uri", ""))})
    elif method == "tools/list":
        return make_response(rid, {"tools": TOOLS})
    elif method == "tools/call":
        content = execute_tool(params.get("name", ""), params.get("arguments", {}))
        return make_response(rid, {"content": content})
    elif method == "prompts/list":
        return make_response(rid, {"prompts": PROMPTS})
    elif method == "prompts/get":
        return make_response(rid, get_prompt(params.get("name", ""), params.get("arguments", {})))
    else:
        return make_error(rid, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check auth token on all MCP endpoints."""
    # Skip auth for health and root endpoints
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    if not _check_auth(request):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized. Pass token via 'Authorization: Bearer <token>' header or '?token=<token>' query param."},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    if isinstance(body, list):
        responses = [r for r in (handle_jsonrpc(req) for req in body) if r is not None]
        return JSONResponse(responses)
    response = handle_jsonrpc(body)
    return Response(status_code=204) if response is None else JSONResponse(response)


@app.get("/mcp")
async def mcp_sse():
    async def stream():
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'notifications/ready'})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/sse")
async def sse_endpoint():
    """SSE endpoint for ChatGPT and Gemini CLI."""
    async def stream():
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'notifications/ready'})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/sse")
async def sse_post_endpoint(request: Request):
    """SSE POST endpoint — same as /mcp POST, for clients that use /sse."""
    body = await request.json()
    if isinstance(body, list):
        responses = [r for r in (handle_jsonrpc(req) for req in body) if r is not None]
        return JSONResponse(responses)
    response = handle_jsonrpc(body)
    return Response(status_code=204) if response is None else JSONResponse(response)


@app.get("/health")
async def health():
    packs = _filter_packs(list_packs())
    auth_enabled = _AUTH_TOKEN is not None
    return {
        "status": "ok",
        "version": __version__,
        "packs": len(packs),
        "packs_dir": str(get_packs_dir()),
        "auth_enabled": auth_enabled,
        "read_only": not _WRITE_ENABLED,
        "scoped": _ALLOWED_PACKS is not None,
    }


@app.get("/")
async def root():
    return {
        "name": "aura",
        "version": __version__,
        "description": "Your portable AI context — MCP Server",
        "endpoints": {
            "/mcp": "MCP protocol (Claude Desktop, Cursor)",
            "/sse": "SSE endpoint (ChatGPT, Gemini CLI)",
            "/health": "Health check",
        },
    }


def run_server(host: str = "localhost", port: int = 3847):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
