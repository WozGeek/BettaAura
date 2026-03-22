<p align="center">
  <br />
  <strong><code>✦ aura</code></strong>
  <br />
  <em>Your portable AI context. One identity across every tool.</em>
  <br /><br />
  <a href="https://pypi.org/project/aura-ctx/"><img alt="PyPI" src="https://img.shields.io/pypi/v/aura-ctx?color=blue&label=PyPI" /></a>
  <a href="https://github.com/WozGeek/BettaAura/actions"><img alt="CI" src="https://github.com/WozGeek/BettaAura/actions/workflows/ci.yml/badge.svg" /></a>
  <a href="https://github.com/WozGeek/BettaAura/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green" /></a>
  <a href="https://pypi.org/project/aura-ctx/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/aura-ctx" /></a>
  <a href="https://github.com/WozGeek/BettaAura/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/WozGeek/BettaAura?style=flat" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#supported-tools">Supported Tools</a> •
  <a href="#commands">Commands</a> •
  <a href="#security">Security</a> •
  <a href="#roadmap">Roadmap</a>
</p>

---

## The Problem

Every AI tool builds a separate picture of who you are. Claude knows your stack but not your writing style. ChatGPT knows your preferences but not your projects. Cursor reads your code but forgets your conventions.

**None of them share context. None of them let you export it. That's lock-in.**

aura fixes this. One CLI. One identity. Every tool.

## Quick Start

```bash
pip install aura-ctx
aura quickstart
```

That's it. `quickstart` does three things:

1. **Scans** your machine — detects languages, frameworks, tools, projects, editor, git identity
2. **Onboards** you — 5 questions to capture your style, role, and rules
3. **Serves** your context to Claude Desktop, ChatGPT, Cursor, and Gemini via MCP

30 seconds. No Docker. No Postgres. No cloud account.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐
│  aura scan   │────▶│ Context Packs│────▶│     MCP Server           │
│  aura onboard│     │  (YAML)      │     │  localhost:3847          │
└──────────────┘     └──────────────┘     └──────┬───────────────────┘
                                                  │
                            ┌─────────────────────┼─────────────────────┐
                            │                     │                     │
                      ┌─────▼─────┐    ┌──────────▼──┐    ┌───────────▼──┐
                      │  Claude   │    │   ChatGPT   │    │   Cursor     │
                      │  Desktop  │    │   Desktop   │    │   IDE        │
                      └───────────┘    └─────────────┘    └──────────────┘
```

### Context Packs

aura organizes your identity into **scoped YAML packs** — `developer`, `writer`, `work`, or any custom domain:

```yaml
# ~/.aura/packs/developer.yaml
name: developer
scope: development
facts:
  - key: languages.primary
    value: [TypeScript, Python]
    type: skill
    confidence: high
  - key: editor
    value: Cursor
    type: preference
  - key: frameworks
    value: [Next.js, FastAPI, Tailwind, Supabase]
    type: skill
rules:
  - instruction: Always use TypeScript over JavaScript
    priority: 8
```

You own these files. Human-readable. Version-controllable. They never leave your machine.

## Supported Tools

| Tool | Setup | Transport |
|------|-------|-----------|
| **Claude Desktop** | `aura setup` — auto-configured | Streamable HTTP |
| **Cursor IDE** | `aura setup` — auto-configured | Streamable HTTP |
| **Gemini CLI** | `aura setup` — auto-configured | SSE |
| **ChatGPT Desktop** | Developer Mode instructions | SSE |
| **Any MCP client** | Manual config | HTTP / SSE |

```bash
aura setup   # writes config for all supported tools
aura serve   # starts MCP server on localhost:3847
```

<details>
<summary><strong>Claude Desktop config</strong></summary>

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```
</details>

<details>
<summary><strong>Cursor IDE config</strong></summary>

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```
</details>

<details>
<summary><strong>Gemini CLI config</strong></summary>

```json
{
  "mcpServers": {
    "aura": { "uri": "http://localhost:3847/sse" }
  }
}
```
</details>

## Commands

| Command | Description |
|---------|-------------|
| `aura quickstart` | Full setup: scan → onboard → configure → serve |
| `aura scan [dirs]` | Auto-detect your stack from your machine |
| `aura onboard` | 5 questions to generate your context |
| `aura serve` | Start the MCP server |
| `aura setup` | Auto-configure Claude, Cursor, Gemini, ChatGPT |
| `aura list` | List all context packs |
| `aura show <pack>` | Display a pack |
| `aura add <pack> <key> <value>` | Add a fact without editing YAML |
| `aura edit <pack>` | Open in $EDITOR |
| `aura doctor` | Check pack health — bloat, stale facts, duplicates |
| `aura export <packs> -f <fmt>` | Export to system-prompt, cursorrules, chatgpt, claude |
| `aura import -s <src> <file>` | Import from ChatGPT or Claude data export |
| `aura extract <file>` | Deep-extract facts using a local LLM |
| `aura diff <a> <b>` | Compare two packs |
| `aura delete <pack>` | Delete a pack |

## Security

aura is local-first by design.

```bash
aura serve                                    # localhost only, no auth
aura serve --token my-secret                  # require Bearer token
aura serve --packs developer,writer           # serve only specific packs
aura serve --read-only                        # disable writes via MCP
aura serve --token s3cret --packs dev --read-only  # combine all
```

- Binds to `127.0.0.1` only — not accessible from the network
- Optional `Bearer` token auth on all endpoints
- Scoped serving — expose only the packs you choose
- Read-only mode — AI reads your context, never modifies it
- `AURA_TOKEN` env var for scripts and CI
- **No telemetry. No analytics. No cloud.**

## Import & Export

```bash
# Import from platform exports
aura import -s chatgpt ~/Downloads/chatgpt-export.zip
aura import -s claude  ~/Downloads/conversations.json

# Export to any format
aura export developer -f system-prompt    # Universal LLM prompt
aura export developer -f cursorrules      # Cursor .cursorrules
aura export developer -f chatgpt          # ChatGPT custom instructions
aura export developer -f claude           # Claude memory statements
```

## Deep Extraction

Extract structured facts from raw conversations using a local LLM:

```bash
aura extract conversations.json --provider ollama --model llama3
```

## Architecture

```
aura/
├── cli.py           # 20 commands (Typer)
├── schema.py        # ContextPack, Fact, Rule (Pydantic)
├── scanner.py       # Machine scanner
├── onboard.py       # Interactive onboarding
├── pack.py          # Pack CRUD
├── mcp_server.py    # FastAPI MCP server (HTTP + SSE)
├── setup.py         # Tool auto-configuration
├── doctor.py        # Pack health checker
├── extractor.py     # LLM-based extraction
├── diff.py          # Pack comparison
├── exporters/       # 4 export formats
└── importers/       # ChatGPT + Claude importers
```

**5,475 lines · 74 tests · 20 commands · MIT license**

## Roadmap

- [x] Machine scanner — languages, frameworks, tools, projects
- [x] Context packs with typed facts and confidence levels
- [x] MCP server (resources, tools, prompts)
- [x] Claude Desktop + Cursor auto-configuration
- [x] ChatGPT Desktop + Gemini CLI support
- [x] Token auth, scoped serving, read-only mode
- [x] Import from ChatGPT + Claude exports
- [x] LLM-based deep extraction (Ollama / OpenAI)
- [x] Pack health checker (`aura doctor`)
- [x] Token-efficient compact profile
- [ ] TypeScript / npm package
- [ ] File watcher for live sync
- [ ] JSON Schema spec for context packs
- [ ] Cloud sync (opt-in)
- [ ] Team context sharing

## Contributing

```bash
git clone https://github.com/WozGeek/BettaAura.git
cd BettaAura
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
