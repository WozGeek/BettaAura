# ✦ aura

![CI](https://github.com/WozGeek/BettaAura/actions/workflows/ci.yml/badge.svg)
[![PyPI](https://img.shields.io/pypi/v/aura-ctx)](https://pypi.org/project/aura-ctx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Your AI tools don't talk to each other. aura fixes that.**

---

You use Claude for analysis, ChatGPT for writing, Cursor for coding. Each one builds a different picture of who you are — your stack, your style, your preferences. None of them share it. When you switch tools, you start from zero.

aura is an open-source CLI that scans your machine, builds your AI identity automatically, and serves it to every tool via MCP. Define yourself once. Every AI knows you instantly.

```bash
pip install aura-ctx
aura scan
aura serve
# → Claude Desktop, Cursor read your context automatically
```

## 30-Second Demo

```bash
$ aura scan ~/Documents

✦ Scan complete

Detected:
  ● identity.name: Enoch A.
  ● editor: Cursor
  ● ai_tools: Claude Desktop, Cursor
  ● languages.primary: TypeScript, JavaScript, Python
  ● frameworks: Next.js, React, Tailwind CSS, Supabase, FastAPI
  ● projects.recent: elison-v01, aura, hotepia

✦ Saved: developer (12 facts)

$ aura serve

✦ aura MCP server running
  Serving 3 context packs
  Claude Desktop, Cursor connected
```

Open Claude Desktop. Ask anything. It already knows your stack, your projects, your style — without you saying a word.

## Why aura Exists

**The problem is fragmentation.** Claude remembers your coding style. ChatGPT knows your writing tone. Cursor has your framework preferences. None of them talk to each other. When you change tools, switch accounts, or start a new AI — you lose everything.

**The problem is opacity.** Platform memories are black boxes. You don't know what they stored, you can't version it, you can't audit it. When ChatGPT gives you a weird answer based on a misremembered fact from three months ago, you have no idea why.

**The problem is lock-in.** The more you use one AI, the more it "knows" you, the harder it is to leave. That's not a feature — it's a trap.

**aura gives you control.** Your context lives on your machine as readable YAML files. You decide what's shared, with which tool, and you can change it anytime. Local-first. No cloud. No tracking.

## Quick Start

```bash
# Install
pip install aura-ctx

# Scan your machine — auto-detects your stack
aura scan

# Answer 5 quick questions for style & preferences
aura onboard

# Connect Claude Desktop & Cursor automatically
aura setup

# Start serving your context
aura serve
```

Or do it all at once:

```bash
aura quickstart
```

## How It Works

aura creates **context packs** — scoped YAML files that describe who you are in a specific domain:

```yaml
# ~/.aura/packs/developer.yaml
name: developer
scope: development
facts:
  - key: languages.primary
    value: [TypeScript, Python]
    type: skill
    confidence: high
  - key: frameworks
    value: [Next.js 15, FastAPI, Supabase]
  - key: editor
    value: Cursor
rules:
  - instruction: "Always use TypeScript strict mode"
    priority: 8
  - instruction: "Dark theme by default — use CSS variables"
    priority: 8
```

Export to any format:

```bash
aura export developer --format cursorrules           # Cursor IDE
aura export developer --format claude-memory         # Claude
aura export developer --format chatgpt-instructions  # ChatGPT
aura export developer --format system-prompt         # Any LLM / Gemini
```

Or serve via MCP and Claude, ChatGPT, Cursor, and Gemini read your context automatically:

```bash
aura serve
```

## Commands

| Command | Description |
|---------|-------------|
| `aura init` | Initialize aura |
| `aura scan [dirs]` | Auto-detect your stack from your machine |
| `aura onboard` | 5 questions to generate your context |
| `aura quickstart` | Scan + onboard + setup in one command |
| `aura create <name>` | Create a pack manually |
| `aura add <pack> <key> <value>` | Add a fact without editing YAML |
| `aura list` | List all packs |
| `aura show <name>` | Display a pack |
| `aura edit <name>` | Open in $EDITOR |
| `aura export <names...> -f <format>` | Export to platform format |
| `aura import -s <source> <file>` | Import from ChatGPT export |
| `aura diff <a> <b>` | Compare two packs |
| `aura doctor` | Check pack health — bloat, stale facts, duplicates |
| `aura setup` | Auto-configure Claude Desktop + Cursor |
| `aura serve` | Start MCP server |
| `aura delete <name>` | Delete a pack |

## The MCP Server

aura includes a full MCP (Model Context Protocol) server. Start it once, and every MCP-compatible tool reads your context automatically:

```bash
aura setup   # writes config for Claude Desktop, Cursor, Gemini CLI
aura serve   # starts the server on localhost:3847
```

### Claude Desktop

Config is written automatically by `aura setup`. Manual path: `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "aura": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:3847/mcp"]
    }
  }
}
```

### ChatGPT Desktop

Requires a Plus or Pro subscription with Developer Mode enabled:

1. Open ChatGPT Desktop → Settings → Connectors → Advanced → **Developer Mode**
2. Add a new MCP connector with SSE URL: `http://localhost:3847/sse`
3. Start `aura serve` and ChatGPT reads your context automatically

### Cursor IDE

Config is written automatically by `aura setup`. Manual path: `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```

### Gemini CLI

Config is written automatically by `aura setup`. Or manually:
```bash
gemini mcp add --transport sse aura http://localhost:3847/sse
```

Or add to `~/.gemini/settings.json`:
```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/sse" }
  }
}
```

The server exposes:
- **Resources**: each pack as a readable resource
- **Tools**: `search_context`, `get_context_pack`, `get_user_profile`, `list_scopes`
- **Prompts**: `with_context` to inject your full identity

## Philosophy

1. **Local-first.** Your context lives on your machine. No cloud, no account, no tracking.
2. **Problem-first.** Your AI tools don't talk to each other. That's the problem we solve.
3. **Scoped, not monolithic.** Separate packs for separate domains. Your dev context doesn't leak into health questions.
4. **Human-controlled.** aura never writes to your packs without asking. You review everything.
5. **Lean by design.** 30-50 facts per pack, not 500. `aura doctor` tells you when to clean up.

## Roadmap

- [x] Core schema & context packs
- [x] CLI with 18 commands
- [x] `aura scan` — auto-detect stack from machine
- [x] `aura onboard` — 5-question interactive setup
- [x] `aura quickstart` — full onboarding in one command
- [x] `aura setup` — auto-configure Claude Desktop + Cursor
- [x] `aura doctor` — pack health checker
- [x] `aura add` — add facts without editing YAML
- [x] MCP server with resources, tools, and prompts
- [x] 4 export formats: system-prompt, cursorrules, claude-memory, chatgpt-instructions
- [x] ChatGPT import (heuristic extraction)
- [x] LLM-powered deep extraction
- [x] Diff engine
- [x] 65+ tests, CI, MIT license
- [ ] Claude conversation import
- [ ] AGENTS.md export
- [ ] `aura watch` — suggest new facts from recent conversations
- [ ] Web dashboard for visual pack editing
- [ ] Chrome extension for claude.ai / chatgpt.com

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

## License

MIT — Built by [WozGeek](https://github.com/WozGeek)
