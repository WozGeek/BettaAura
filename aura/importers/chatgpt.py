"""
Import context from ChatGPT data exports.

ChatGPT's "Export your data" feature produces a ZIP containing:
- conversations.json — all conversation history
- user.json — account info
- model_comparisons.json
- message_feedback.json

This importer reads conversations.json and extracts facts
using heuristic pattern matching (no LLM required for basic mode).
For deeper extraction, use `aura extract` which uses a local LLM.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Optional

from aura.schema import Confidence, ContextPack, Fact, FactType, PackMeta


def import_chatgpt_export(
    source: str | Path,
    pack_name: str = "chatgpt-import",
    scope: str = "general",
    max_conversations: Optional[int] = None,
) -> ContextPack:
    """
    Import context from a ChatGPT data export.

    Args:
        source: Path to conversations.json or the full export .zip
        pack_name: Name for the resulting context pack
        scope: Scope to assign to the pack
        max_conversations: Limit number of conversations to process

    Returns:
        A ContextPack with extracted facts
    """
    source = Path(source)

    # Handle ZIP or direct JSON
    if source.suffix == ".zip":
        conversations = _load_from_zip(source)
    elif source.suffix == ".json":
        with open(source) as f:
            conversations = json.load(f)
    else:
        raise ValueError(f"Unsupported file format: {source.suffix}. Expected .zip or .json")

    if max_conversations:
        conversations = conversations[:max_conversations]

    # Extract user messages
    user_messages = _extract_user_messages(conversations)

    # Run heuristic extraction
    facts = _extract_facts_heuristic(user_messages)

    # Build stats
    stats = _compute_stats(conversations, user_messages)

    return ContextPack(
        name=pack_name,
        scope=scope,
        facts=facts,
        rules=[],
        meta=PackMeta(
            description=f"Imported from ChatGPT export ({stats['total_conversations']} conversations, {stats['total_user_messages']} messages)",
            tags=["chatgpt", "import", "auto-extracted"],
        ),
    )


def _load_from_zip(zip_path: Path) -> list[dict]:
    """Extract conversations.json from a ChatGPT export ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        # Look for conversations.json in the ZIP
        for name in zf.namelist():
            if name.endswith("conversations.json"):
                with zf.open(name) as f:
                    return json.loads(f.read())
    raise FileNotFoundError("conversations.json not found in ZIP archive")


def _extract_user_messages(conversations: list[dict]) -> list[str]:
    """Extract all user-authored messages from conversations."""
    messages = []
    for conv in conversations:
        mapping = conv.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if msg and msg.get("author", {}).get("role") == "user":
                parts = msg.get("content", {}).get("parts", [])
                for part in parts:
                    if isinstance(part, str) and len(part.strip()) > 5:
                        messages.append(part.strip())
    return messages


def _extract_facts_heuristic(messages: list[str]) -> list[Fact]:
    """
    Extract facts from user messages using pattern matching.

    This is the basic (no-LLM) extractor. It looks for common patterns
    like "I use X", "I'm a Y", "I prefer Z", etc.
    """
    facts: list[Fact] = []
    seen_keys: set[str] = set()

    # --- Programming languages ---
    lang_counter: Counter = Counter()
    lang_patterns = [
        r"\b(?:I (?:use|code in|write|program in|work with))\s+(\w+)",
        r"\b(?:in|using|with)\s+(Python|TypeScript|JavaScript|Rust|Go|Java|C\+\+|Ruby|PHP|Swift|Kotlin)\b",
    ]
    for msg in messages:
        for pattern in lang_patterns:
            for match in re.finditer(pattern, msg, re.IGNORECASE):
                lang = match.group(1).strip()
                if lang.lower() in _KNOWN_LANGUAGES:
                    lang_counter[lang] += 1

    if lang_counter:
        top_langs = [lang for lang, _ in lang_counter.most_common(5)]
        facts.append(Fact(
            key="languages.detected",
            value=top_langs,
            type=FactType.SKILL,
            confidence=Confidence.MEDIUM,
            source="chatgpt-import",
        ))

    # --- Frameworks ---
    framework_counter: Counter = Counter()
    for msg in messages:
        for fw in _KNOWN_FRAMEWORKS:
            if fw.lower() in msg.lower():
                framework_counter[fw] += 1

    if framework_counter:
        top_fw = [fw for fw, count in framework_counter.most_common(8) if count >= 2]
        if top_fw:
            facts.append(Fact(
                key="frameworks.detected",
                value=top_fw,
                type=FactType.SKILL,
                confidence=Confidence.MEDIUM,
                source="chatgpt-import",
            ))

    # --- Self-identification patterns ---
    role_patterns = [
        (r"I(?:'m| am) (?:a|an) (\w+(?:\s+\w+){0,3}(?:developer|engineer|designer|manager|founder|student|researcher|writer|analyst))", "role"),
        (r"I work (?:at|for) ([\w\s&.]+?)(?:\.|,|$)", "company"),
        (r"I(?:'m| am) (?:learning|studying) ([\w\s]+?)(?:\.|,|$)", "learning"),
    ]
    for msg in messages:
        for pattern, key in role_patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match and key not in seen_keys:
                value = match.group(1).strip()
                if len(value) > 2 and len(value) < 60:
                    facts.append(Fact(
                        key=key,
                        value=value,
                        type=FactType.IDENTITY if key in ("role", "company") else FactType.SKILL,
                        confidence=Confidence.LOW,
                        source="chatgpt-import",
                    ))
                    seen_keys.add(key)

    # --- Preference patterns ---
    pref_patterns = [
        (r"I (?:prefer|like|want|always use) ([\w\s]+?)(?:\.|,|$|because|over)", "preference"),
    ]
    pref_values: list[str] = []
    for msg in messages:
        for pattern, _ in pref_patterns:
            for match in re.finditer(pattern, msg, re.IGNORECASE):
                value = match.group(1).strip()
                if 3 < len(value) < 80:
                    pref_values.append(value)

    # Deduplicate and take most common preferences
    if pref_values:
        pref_counter = Counter(pref_values)
        top_prefs = [p for p, count in pref_counter.most_common(5) if count >= 2]
        for pref in top_prefs:
            facts.append(Fact(
                key="preferences.detected",
                value=pref,
                type=FactType.PREFERENCE,
                confidence=Confidence.LOW,
                source="chatgpt-import",
            ))

    # --- Conversation topic analysis ---
    topic_counter: Counter = Counter()
    for msg in messages:
        msg_lower = msg.lower()
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                topic_counter[topic] += 1

    if topic_counter:
        top_topics = [t for t, count in topic_counter.most_common(5) if count >= 3]
        if top_topics:
            facts.append(Fact(
                key="topics.frequent",
                value=top_topics,
                type=FactType.CONTEXT,
                confidence=Confidence.MEDIUM,
                source="chatgpt-import",
            ))

    return facts


def _compute_stats(conversations: list[dict], user_messages: list[str]) -> dict:
    """Compute basic stats about the export."""
    return {
        "total_conversations": len(conversations),
        "total_user_messages": len(user_messages),
    }


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
_KNOWN_LANGUAGES = {
    "python", "typescript", "javascript", "rust", "go", "golang", "java",
    "c++", "cpp", "ruby", "php", "swift", "kotlin", "scala", "r",
    "julia", "dart", "lua", "perl", "haskell", "elixir", "clojure",
    "zig", "nim", "ocaml", "c#", "csharp", "sql", "html", "css",
}

_KNOWN_FRAMEWORKS = [
    "React", "Next.js", "Vue", "Nuxt", "Angular", "Svelte", "SvelteKit",
    "Django", "Flask", "FastAPI", "Express", "Nest.js", "Rails",
    "Spring", "Laravel", "Tailwind", "Bootstrap",
    "TensorFlow", "PyTorch", "LangChain", "LlamaIndex",
    "Prisma", "Drizzle", "SQLAlchemy", "Supabase", "Firebase",
    "Docker", "Kubernetes", "Terraform",
]

_TOPIC_KEYWORDS = {
    "web-development": ["react", "html", "css", "frontend", "backend", "api", "rest"],
    "machine-learning": ["model", "training", "dataset", "neural", "llm", "gpt", "embedding"],
    "devops": ["docker", "kubernetes", "ci/cd", "deploy", "aws", "gcp", "azure"],
    "mobile": ["ios", "android", "react native", "flutter", "swift", "kotlin"],
    "data": ["pandas", "sql", "database", "query", "csv", "analytics"],
    "design": ["figma", "ui", "ux", "layout", "wireframe", "mockup"],
    "writing": ["blog", "article", "essay", "copy", "content", "draft"],
    "business": ["startup", "revenue", "strategy", "market", "pitch", "investor"],
}
