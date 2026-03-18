"""
aura.mcp_server — Model Context Protocol Server

Serves your context packs to any MCP-compatible AI client.
Run with: aura serve --mcp

Exposes context packs as:
  - Resources: each pack is a readable resource
  - Tools: query, search, and mutate packs programmatically
  - Prompts: pre-built prompt templates that include your context

Protocol spec: https://modelcontextprotocol.io/specification/2025-11-25
"""

from __future__ import annotations

import json
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
        "name": "get_context",
        "description": (
            "Get the user's full context for a specific scope/domain. "
            "Returns structured facts and rules. Use this to understand who you're talking to."
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
            "Get ALL of the user's context packs combined. "
            "Use this at the start of a conversation to fully understand the user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scopes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: filter to specific scopes. Empty = all.",
                },
            },
        },
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
    if name == "get_context":
        pack_name = arguments["pack_name"]
        if not pack_exists(pack_name):
            return [{"type": "text", "text": f"Pack '{pack_name}' not found. Use list_packs to see available packs."}]
        pack = load_pack(pack_name)
        return [{"type": "text", "text": pack.to_system_prompt()}]

    elif name == "get_all_context":
        packs = list_packs()
        scopes = arguments.get("scopes", [])
        if scopes:
            packs = [p for p in packs if p.scope in scopes]
        if not packs:
            return [{"type": "text", "text": "No context packs found."}]
        return [{"type": "text", "text": export_system_prompt(packs, include_header=False)}]

    elif name == "search_context":
        query = arguments["query"].lower()
        results = []
        for pack in list_packs():
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
        pack_name = arguments["pack_name"]
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
        pack_name = arguments["pack_name"]
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
        packs = list_packs()
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
    for pack in list_packs():
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
        packs = list_packs()
        return [{"uri": uri, "mimeType": "text/plain", "text": export_system_prompt(packs)}]
    if uri.startswith("aura://packs/"):
        name = uri.replace("aura://packs/", "")
        if pack_exists(name):
            pack = load_pack(name)
            return [{"uri": uri, "mimeType": "text/plain", "text": pack.to_system_prompt()}]
    return [{"uri": uri, "mimeType": "text/plain", "text": f"Resource not found: {uri}"}]


# ---------------------------------------------------------------------------
# Prompt execution
# ---------------------------------------------------------------------------
def get_prompt(name: str, arguments: dict) -> dict:
    if name == "with_full_context":
        packs = list_packs()
        content = export_system_prompt(packs, include_header=False)
        return {
            "description": "Full user context",
            "messages": [{"role": "user", "content": {"type": "text", "text": f"Here is my personal context:\n\n{content}"}}],
        }
    elif name == "with_scope":
        scope = arguments.get("scope", "")
        packs = [p for p in list_packs() if p.scope == scope or p.name == scope]
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


@app.get("/health")
async def health():
    packs = list_packs()
    return {"status": "ok", "version": __version__, "packs": len(packs), "packs_dir": str(get_packs_dir())}


@app.get("/")
async def root():
    return {"name": "aura", "version": __version__, "description": "Your portable AI context — MCP Server", "endpoints": {"/mcp": "MCP protocol", "/health": "Health check"}}


def run_server(host: str = "localhost", port: int = 3847):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
