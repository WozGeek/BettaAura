"""
aura.pack — Context Pack Manager

Handles creating, reading, writing, listing, and validating context packs
on the local filesystem. Packs are stored as YAML files in ~/.aura/packs/.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from aura.schema import ContextPack, Fact, PackMeta, Rule
from aura.schema_export import validate_pack_data

yaml = YAML()
yaml.default_flow_style = False
yaml.allow_unicode = True


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def get_aura_home() -> Path:
    """Return the aura home directory (~/.aura)."""
    home = Path.home() / ".aura"
    return home


def get_packs_dir() -> Path:
    """Return the packs directory (~/.aura/packs)."""
    return get_aura_home() / "packs"


def get_config_path() -> Path:
    """Return the global config file path."""
    return get_aura_home() / "config.yaml"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def init_aura() -> Path:
    """Initialize the aura directory structure. Returns aura home path."""
    home = get_aura_home()
    packs_dir = get_packs_dir()

    home.mkdir(parents=True, exist_ok=True)
    packs_dir.mkdir(parents=True, exist_ok=True)

    # Create default config if missing
    config_path = get_config_path()
    if not config_path.exists():
        config = {
            "aura": {
                "version": "0.1.0",
                "default_export_format": "system-prompt",
                "editor": None,  # Will use $EDITOR
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config, f)

    return home


def is_initialized() -> bool:
    """Check if aura has been initialized."""
    return get_aura_home().exists() and get_packs_dir().exists()


# ---------------------------------------------------------------------------
# Pack CRUD
# ---------------------------------------------------------------------------
def _pack_path(name: str) -> Path:
    """Get the file path for a named pack."""
    return get_packs_dir() / f"{name}.yaml"


def pack_exists(name: str) -> bool:
    """Check if a pack with this name exists."""
    return _pack_path(name).exists()


def save_pack(pack: ContextPack) -> Path:
    """Save a context pack to disk as YAML. Returns the file path."""
    path = _pack_path(pack.name)

    # Convert to dict for YAML serialization
    data = {
        "name": pack.name,
        "scope": pack.scope,
        "meta": {
            "schema_version": pack.meta.schema_version,
            "created_at": pack.meta.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    }

    if pack.meta.description:
        data["meta"]["description"] = pack.meta.description

    if pack.meta.tags:
        data["meta"]["tags"] = pack.meta.tags

    if pack.facts:
        data["facts"] = []
        for fact in pack.facts:
            fact_data: dict = {
                "key": fact.key,
                "value": fact.value,
            }
            if fact.type.value != "context":
                fact_data["type"] = fact.type.value
            if fact.confidence.value != "high":
                fact_data["confidence"] = fact.confidence.value
            if fact.source:
                fact_data["source"] = fact.source
            data["facts"].append(fact_data)

    if pack.rules:
        data["rules"] = []
        for rule in pack.rules:
            rule_data: dict = {"instruction": rule.instruction}
            if rule.priority > 0:
                rule_data["priority"] = rule.priority
            data["rules"].append(rule_data)

    with open(path, "w") as f:
        yaml.dump(data, f)

    return path


def load_pack(name: str) -> ContextPack:
    """Load a context pack from disk."""
    path = _pack_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Pack '{name}' not found at {path}")

    with open(path) as f:
        data = yaml.load(f)

    # Validate against JSON Schema before parsing
    errors = validate_pack_data(data)
    if errors:
        error_list = "\n  ".join(errors)
        raise ValueError(
            f"Pack '{name}' failed schema validation:\n  {error_list}\n"
            f"Fix the YAML file at: {path}"
        )

    # Parse facts
    facts = []
    for f_data in data.get("facts", []):
        facts.append(Fact(
            key=f_data["key"],
            value=f_data["value"],
            type=f_data.get("type", "context"),
            confidence=f_data.get("confidence", "high"),
            source=f_data.get("source"),
        ))

    # Parse rules
    rules = []
    for r_data in data.get("rules", []):
        rules.append(Rule(
            instruction=r_data["instruction"],
            priority=r_data.get("priority", 0),
        ))

    # Parse meta
    meta_data = data.get("meta", {})
    meta = PackMeta(
        schema_version=meta_data.get("schema_version", "0.1.0"),
        created_at=datetime.fromisoformat(meta_data["created_at"]) if "created_at" in meta_data else datetime.now(),
        updated_at=datetime.fromisoformat(meta_data["updated_at"]) if "updated_at" in meta_data else datetime.now(),
        description=meta_data.get("description"),
        tags=meta_data.get("tags", []),
    )

    return ContextPack(
        name=data["name"],
        scope=data["scope"],
        facts=facts,
        rules=rules,
        meta=meta,
    )


def list_packs() -> list[ContextPack]:
    """List all available context packs."""
    packs_dir = get_packs_dir()
    if not packs_dir.exists():
        return []

    packs = []
    for path in sorted(packs_dir.glob("*.yaml")):
        try:
            pack = load_pack(path.stem)
            packs.append(pack)
        except Exception:
            continue  # Skip malformed packs
    return packs


def delete_pack(name: str) -> bool:
    """Delete a context pack. Returns True if deleted."""
    path = _pack_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES: dict[str, dict] = {
    # -----------------------------------------------------------------
    # General-purpose
    # -----------------------------------------------------------------
    "developer": {
        "scope": "development",
        "description": "General-purpose development context — languages, frameworks, coding style.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill"},
            {"key": "languages.learning", "value": ["Rust"], "type": "skill"},
            {"key": "frameworks", "value": ["Next.js", "FastAPI"], "type": "skill"},
            {"key": "editor", "value": "VS Code / Cursor", "type": "preference"},
            {"key": "style.comments", "value": "Minimal — only for non-obvious logic", "type": "style"},
            {"key": "style.formatting", "value": "Prefer explicit types over inference", "type": "style"},
            {"key": "testing", "value": "Integration tests over unit tests when possible", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always use strict TypeScript (no 'any')", "priority": 8},
            {"instruction": "Prefer functional patterns over OOP where reasonable", "priority": 5},
            {"instruction": "Use descriptive variable names — no single letters except in loops", "priority": 6},
            {"instruction": "Add error handling with specific error types, not generic catches", "priority": 7},
        ],
    },
    "writer": {
        "scope": "writing",
        "description": "Your writing style and content preferences.",
        "facts": [
            {"key": "tone", "value": "Direct, no fluff, occasional sharp humor", "type": "style"},
            {"key": "audience", "value": "Technical professionals", "type": "context"},
            {"key": "formatting", "value": "Short paragraphs, concrete examples, minimal headers", "type": "style"},
            {"key": "languages", "value": ["English", "French"], "type": "skill"},
        ],
        "rules": [
            {"instruction": "Avoid corporate jargon and buzzwords", "priority": 8},
            {"instruction": "Use active voice", "priority": 6},
            {"instruction": "Lead with the conclusion, then explain", "priority": 7},
            {"instruction": "Keep paragraphs under 4 sentences", "priority": 5},
        ],
    },
    "researcher": {
        "scope": "research",
        "description": "Research interests and methodology preferences.",
        "facts": [
            {"key": "domains", "value": ["AI/ML", "distributed systems"], "type": "context"},
            {"key": "methodology", "value": "Evidence-based, prefer primary sources", "type": "style"},
            {"key": "citation_style", "value": "Inline with links", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always cite sources with links when available", "priority": 8},
            {"instruction": "Distinguish between established facts and speculation", "priority": 9},
            {"instruction": "Present contrarian viewpoints alongside mainstream ones", "priority": 6},
        ],
    },
    "work": {
        "scope": "work",
        "description": "Professional context — role, company, communication style.",
        "facts": [
            {"key": "role", "value": "Software Engineer", "type": "identity"},
            {"key": "company", "value": "Acme Corp", "type": "identity"},
            {"key": "team", "value": "Platform team", "type": "context"},
            {"key": "communication.style", "value": "Concise, data-driven", "type": "style"},
        ],
        "rules": [
            {"instruction": "Frame recommendations with business impact", "priority": 7},
            {"instruction": "Include time estimates for technical suggestions", "priority": 5},
        ],
    },
    # -----------------------------------------------------------------
    # Stack-specific
    # -----------------------------------------------------------------
    "frontend": {
        "scope": "development",
        "description": "Frontend development — React/Next.js, TypeScript, Tailwind, modern web stack.",
        "facts": [
            {"key": "languages.primary", "value": ["TypeScript", "JavaScript"], "type": "skill"},
            {"key": "frameworks", "value": ["Next.js", "React", "Tailwind CSS", "Vite"], "type": "skill"},
            {"key": "editor", "value": "Cursor", "type": "preference"},
            {"key": "style.design", "value": "Mobile-first, dark themes, minimal UI", "type": "style"},
            {"key": "state_management", "value": "React Server Components when possible, Zustand for client state", "type": "preference"},
            {"key": "testing", "value": "Playwright for E2E, Vitest for unit", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always use TypeScript strict mode — no 'any', no implicit returns", "priority": 9},
            {"instruction": "Use Tailwind utility classes only — no custom CSS unless unavoidable", "priority": 8},
            {"instruction": "Prefer Server Components by default, use 'use client' only when needed", "priority": 8},
            {"instruction": "Mobile-first responsive design — start from smallest viewport", "priority": 7},
            {"instruction": "Accessibility first — semantic HTML, ARIA labels, keyboard navigation", "priority": 7},
            {"instruction": "Dark theme by default — use CSS variables for all colors", "priority": 6},
        ],
    },
    "backend": {
        "scope": "development",
        "description": "Backend development — APIs, databases, infrastructure, Python or Node.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill"},
            {"key": "frameworks", "value": ["FastAPI", "SQLAlchemy", "Pydantic"], "type": "skill"},
            {"key": "databases", "value": ["PostgreSQL", "Redis"], "type": "skill"},
            {"key": "infrastructure", "value": ["Docker", "GitHub Actions"], "type": "skill"},
            {"key": "api_style", "value": "REST with OpenAPI spec, considering GraphQL for complex queries", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always validate input with Pydantic models or Zod schemas — never trust raw input", "priority": 9},
            {"instruction": "Write database migrations for every schema change — no manual ALTER TABLE", "priority": 8},
            {"instruction": "Every endpoint needs error handling with proper HTTP status codes", "priority": 8},
            {"instruction": "Log at structured levels (info, warning, error) — no print() in production", "priority": 7},
            {"instruction": "Write integration tests against a real database, not mocks", "priority": 6},
        ],
    },
    "data-scientist": {
        "scope": "analysis",
        "description": "Data science, ML, and analytics — Python, notebooks, visualization.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "SQL"], "type": "skill"},
            {"key": "tools", "value": ["pandas", "NumPy", "scikit-learn", "Jupyter", "matplotlib"], "type": "skill"},
            {"key": "ml_frameworks", "value": ["PyTorch", "Hugging Face Transformers"], "type": "skill"},
            {"key": "visualization", "value": ["matplotlib", "seaborn", "Plotly"], "type": "preference"},
            {"key": "data_sources", "value": ["PostgreSQL", "CSV/Parquet", "REST APIs"], "type": "context"},
        ],
        "rules": [
            {"instruction": "Always cite data sources — never invent numbers or statistics", "priority": 10},
            {"instruction": "Flag assumptions and confidence levels in every analysis", "priority": 9},
            {"instruction": "Prefer charts over tables — explain what the data means, not just what it shows", "priority": 8},
            {"instruction": "Reproducibility matters — include random seeds, version pins, and data checksums", "priority": 8},
            {"instruction": "Start with simple models before reaching for deep learning", "priority": 7},
            {"instruction": "Show your work — include intermediate steps, not just final results", "priority": 6},
        ],
    },
    "mobile": {
        "scope": "development",
        "description": "Mobile development — React Native, Swift, Flutter, cross-platform apps.",
        "facts": [
            {"key": "languages.primary", "value": ["TypeScript", "Swift"], "type": "skill"},
            {"key": "frameworks", "value": ["React Native", "Expo"], "type": "skill"},
            {"key": "platforms", "value": ["iOS", "Android"], "type": "context"},
            {"key": "tools", "value": ["Xcode", "Android Studio", "Flipper"], "type": "preference"},
            {"key": "state_management", "value": "Zustand or React Query for server state", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always handle offline state — assume the network is unreliable", "priority": 9},
            {"instruction": "Test on real devices, not just simulators", "priority": 8},
            {"instruction": "Respect platform conventions — iOS Human Interface Guidelines, Material Design", "priority": 8},
            {"instruction": "Performance first — no unnecessary re-renders, lazy load heavy screens", "priority": 7},
            {"instruction": "Accessibility from day one — VoiceOver, TalkBack, dynamic font sizes", "priority": 7},
        ],
    },
    "devops": {
        "scope": "infrastructure",
        "description": "DevOps and SRE — CI/CD, containers, cloud, monitoring, reliability.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "Bash", "Go"], "type": "skill"},
            {"key": "tools", "value": ["Docker", "Kubernetes", "Terraform", "GitHub Actions"], "type": "skill"},
            {"key": "cloud", "value": ["AWS", "GCP"], "type": "skill"},
            {"key": "monitoring", "value": ["Prometheus", "Grafana", "Datadog"], "type": "preference"},
            {"key": "methodology", "value": "Infrastructure as Code, GitOps, immutable deployments", "type": "style"},
        ],
        "rules": [
            {"instruction": "Everything as code — no manual infrastructure changes, ever", "priority": 10},
            {"instruction": "Every deployment must be reversible — rollback plan before shipping", "priority": 9},
            {"instruction": "Alerts must be actionable — no alert fatigue, no noisy dashboards", "priority": 8},
            {"instruction": "Least privilege by default — no admin credentials in scripts or env vars", "priority": 8},
            {"instruction": "Document runbooks for every critical service — assume you're on-call at 3 AM", "priority": 7},
        ],
    },
    # -----------------------------------------------------------------
    # Role-specific
    # -----------------------------------------------------------------
    "founder": {
        "scope": "product",
        "description": "Indie hacker / founder — product thinking, speed, MVP mindset.",
        "facts": [
            {"key": "role", "value": "Solo founder building an MVP", "type": "identity"},
            {"key": "stack", "value": ["Python", "Next.js", "Supabase", "Vercel"], "type": "skill"},
            {"key": "tools", "value": ["Cursor", "Claude", "ChatGPT", "Linear"], "type": "preference"},
            {"key": "stage", "value": "Pre-launch, iterating fast, seeking product-market fit", "type": "context"},
            {"key": "constraints", "value": "Solo dev, limited budget, time is the bottleneck", "type": "constraint"},
        ],
        "rules": [
            {"instruction": "Always think MVP — ship the smallest thing that tests the hypothesis", "priority": 10},
            {"instruction": "User value over code quality — working > perfect", "priority": 9},
            {"instruction": "Give me the fastest path, not the most elegant one", "priority": 8},
            {"instruction": "When suggesting tools or services, prefer free tiers and open source", "priority": 7},
            {"instruction": "Challenge my assumptions — tell me when an idea won't work", "priority": 7},
        ],
    },
    "student": {
        "scope": "education",
        "description": "Student / learner — studying, building projects, learning new skills.",
        "facts": [
            {"key": "role", "value": "CS student learning to build real projects", "type": "identity"},
            {"key": "languages.learning", "value": ["Python", "JavaScript"], "type": "skill"},
            {"key": "interests", "value": ["AI/ML", "web development", "open source"], "type": "context"},
            {"key": "level", "value": "Intermediate — understands basics, building toward advanced", "type": "context"},
        ],
        "rules": [
            {"instruction": "Explain concepts step by step — don't skip fundamentals", "priority": 9},
            {"instruction": "Always explain WHY, not just HOW — I want to understand the reasoning", "priority": 9},
            {"instruction": "When showing code, include comments explaining non-obvious parts", "priority": 8},
            {"instruction": "Suggest projects or exercises to practice new concepts", "priority": 7},
            {"instruction": "Point me to official docs and good learning resources when relevant", "priority": 6},
            {"instruction": "Don't do my homework — guide me to the answer instead", "priority": 8},
        ],
    },
    "marketer": {
        "scope": "marketing",
        "description": "Content marketer / growth — copywriting, SEO, social media, analytics.",
        "facts": [
            {"key": "role", "value": "Content marketer focused on growth", "type": "identity"},
            {"key": "channels", "value": ["Twitter/X", "LinkedIn", "Blog", "Newsletter"], "type": "context"},
            {"key": "tools", "value": ["Google Analytics", "Ahrefs", "Notion", "Canva"], "type": "preference"},
            {"key": "tone", "value": "Conversational, punchy, data-backed", "type": "style"},
            {"key": "audience", "value": "Technical professionals and early adopters", "type": "context"},
        ],
        "rules": [
            {"instruction": "Lead with a hook — first line must stop the scroll", "priority": 9},
            {"instruction": "Back claims with numbers — no vague statements", "priority": 8},
            {"instruction": "Write at an 8th-grade reading level — simple beats clever", "priority": 8},
            {"instruction": "Every piece of content needs a clear CTA", "priority": 7},
            {"instruction": "SEO matters — include keywords naturally, don't stuff them", "priority": 6},
        ],
    },
    "designer": {
        "scope": "design",
        "description": "Product designer / UX — user research, wireframes, design systems.",
        "facts": [
            {"key": "role", "value": "Product designer", "type": "identity"},
            {"key": "tools", "value": ["Figma", "Framer", "Storybook"], "type": "preference"},
            {"key": "methodology", "value": "User-centered design, iterative prototyping", "type": "style"},
            {"key": "focus", "value": "Design systems, interaction design, accessibility", "type": "context"},
        ],
        "rules": [
            {"instruction": "Always start with the user problem, not the solution", "priority": 9},
            {"instruction": "Accessibility is not optional — WCAG 2.1 AA minimum", "priority": 9},
            {"instruction": "When suggesting UI patterns, reference existing design systems (Radix, shadcn)", "priority": 7},
            {"instruction": "Mobile-first wireframes before desktop", "priority": 7},
            {"instruction": "Less is more — remove before adding", "priority": 6},
        ],
    },
    # -----------------------------------------------------------------
    # AI-specific
    # -----------------------------------------------------------------
    "ai-builder": {
        "scope": "development",
        "description": "AI/LLM builder — agents, RAG, fine-tuning, prompt engineering, tooling.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill"},
            {"key": "frameworks", "value": ["LangChain", "LlamaIndex", "Hugging Face", "OpenAI SDK"], "type": "skill"},
            {"key": "tools", "value": ["Ollama", "vLLM", "Claude API", "OpenAI API"], "type": "preference"},
            {"key": "focus", "value": "RAG pipelines, agent systems, MCP servers, prompt optimization", "type": "context"},
            {"key": "models", "value": ["Claude", "GPT-4", "Llama", "Mistral"], "type": "context"},
        ],
        "rules": [
            {"instruction": "Always consider token cost and latency — efficiency matters at scale", "priority": 9},
            {"instruction": "Prefer structured outputs (JSON, XML) over free-text when parsing LLM responses", "priority": 8},
            {"instruction": "Always add retry logic and fallbacks for API calls — LLMs fail", "priority": 8},
            {"instruction": "Eval before shipping — no prompt change without measuring impact", "priority": 8},
            {"instruction": "RAG over fine-tuning unless you have a clear reason to fine-tune", "priority": 7},
            {"instruction": "Show me the prompt — never hide the system prompt in abstractions", "priority": 7},
        ],
    },
}


def create_from_template(template_name: str, pack_name: Optional[str] = None) -> ContextPack:
    """Create a new context pack from a built-in template."""
    if template_name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

    template = TEMPLATES[template_name]
    name = pack_name or template_name

    facts = [Fact(**f, source="template") for f in template["facts"]]
    rules = [Rule(**r) for r in template["rules"]]

    return ContextPack(
        name=name,
        scope=template["scope"],
        facts=facts,
        rules=rules,
        meta=PackMeta(
            description=template["description"],
            tags=[template_name, "template"],
        ),
    )
