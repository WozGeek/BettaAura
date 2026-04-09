"""
Import context from Claude conversation exports.

Claude's data export (from claude.ai Settings → Export Data) produces
a JSON file with conversation history. This importer extracts user
messages and builds context packs using heuristic pattern matching.

For deeper extraction, use `aura extract` which uses a local LLM.

Also supports generic JSON conversation formats (any chat export
with messages containing role + content).
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Optional

from aura.schema import Confidence, ContextPack, Fact, FactType, PackMeta


def import_claude_export(
    source: str | Path,
    pack_name: str = "claude-import",
    scope: str = "general",
    max_conversations: Optional[int] = None,
) -> ContextPack:
    """
    Import context from a Claude data export.

    Supports:
      - JSON file with list of conversations
      - ZIP file containing conversations JSON
      - Single conversation JSON object

    Returns:
        A ContextPack with extracted facts
    """
    source = Path(source)

    if source.suffix == ".zip":
        conversations = _load_from_zip(source)
    elif source.suffix == ".json":
        with open(source) as f:
            data = json.load(f)
        # Handle both list of conversations and single conversation
        if isinstance(data, list):
            conversations = data
        elif isinstance(data, dict):
            conversations = [data]
        else:
            raise ValueError("Unexpected JSON structure")
    else:
        raise ValueError(f"Unsupported file format: {source.suffix}. Expected .zip or .json")

    if max_conversations:
        conversations = conversations[:max_conversations]

    user_messages = _extract_user_messages(conversations)

    if not user_messages:
        return ContextPack(
            name=pack_name,
            scope=scope,
            facts=[],
            meta=PackMeta(description="Imported from Claude (no messages found)"),
        )

    facts = _extract_facts(user_messages)

    return ContextPack(
        name=pack_name,
        scope=scope,
        facts=facts,
        meta=PackMeta(
            description=f"Imported from Claude — {len(user_messages)} messages, {len(conversations)} conversations",
        ),
    )


def _load_from_zip(zip_path: Path) -> list[dict]:
    """Load conversations from a Claude export ZIP."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        # Look for conversation files
        candidates = [
            n for n in names
            if "conversation" in n.lower() and n.endswith(".json")
        ]

        # Fallback: any JSON file
        if not candidates:
            candidates = [n for n in names if n.endswith(".json")]

        if not candidates:
            raise ValueError(f"No JSON files found in {zip_path}")

        all_conversations = []
        for name in candidates:
            with zf.open(name) as f:
                data = json.loads(f.read())
                if isinstance(data, list):
                    all_conversations.extend(data)
                elif isinstance(data, dict):
                    all_conversations.append(data)

        return all_conversations


def _extract_user_messages(conversations: list[dict]) -> list[str]:
    """Extract user messages from Claude conversations."""
    messages = []

    for conv in conversations:
        # Format 1: Claude export with chat_messages
        if "chat_messages" in conv:
            for msg in conv["chat_messages"]:
                if msg.get("sender") == "human" and msg.get("text"):
                    messages.append(msg["text"])
                elif msg.get("role") == "user" and msg.get("content"):
                    content = msg["content"]
                    if isinstance(content, str):
                        messages.append(content)
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                messages.append(part["text"])

        # Format 2: Standard messages array
        elif "messages" in conv:
            for msg in conv["messages"]:
                role = msg.get("role", msg.get("sender", ""))
                content = msg.get("content", msg.get("text", ""))
                if role in ("user", "human"):
                    if isinstance(content, str):
                        messages.append(content)
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                messages.append(part["text"])

        # Format 3: Flat conversation with content blocks
        elif "content" in conv and conv.get("role") in ("user", "human"):
            content = conv["content"]
            if isinstance(content, str):
                messages.append(content)

    return messages


def _extract_facts(messages: list[str]) -> list[Fact]:
    """Extract structured facts from user messages using heuristics."""
    facts = []
    all_text = " ".join(messages).lower()

    # Language detection
    languages = _detect_languages(all_text)
    if languages:
        facts.append(Fact(
            key="languages.mentioned",
            value=languages,
            type=FactType.SKILL,
            confidence=Confidence.MEDIUM,
            source="claude-import",
        ))

    # Framework detection
    frameworks = _detect_frameworks(all_text)
    if frameworks:
        facts.append(Fact(
            key="frameworks.mentioned",
            value=frameworks,
            type=FactType.SKILL,
            confidence=Confidence.MEDIUM,
            source="claude-import",
        ))

    # Topic analysis
    topics = _detect_topics(messages)
    if topics:
        facts.append(Fact(
            key="topics.frequent",
            value=topics[:8],
            type=FactType.CONTEXT,
            confidence=Confidence.MEDIUM,
            source="claude-import",
        ))

    # Communication style
    style = _detect_style(messages)
    if style:
        for key, value in style.items():
            facts.append(Fact(
                key=f"style.{key}",
                value=value,
                type=FactType.STYLE,
                confidence=Confidence.LOW,
                source="claude-import",
            ))

    # Conversation stats
    facts.append(Fact(
        key="import.message_count",
        value=str(len(messages)),
        type=FactType.CONTEXT,
        confidence=Confidence.HIGH,
        source="claude-import",
    ))

    return facts


# ---------------------------------------------------------------------------
# Detection heuristics (shared patterns with chatgpt importer)
# ---------------------------------------------------------------------------

_LANGUAGE_PATTERNS = {
    "Python": r"\bpython\b",
    "TypeScript": r"\btypescript\b|\b\.tsx?\b",
    "JavaScript": r"\bjavascript\b|\bjs\b|\bnode\.?js\b",
    "Rust": r"\brust\b|\bcargo\b",
    "Go": r"\bgolang\b|\bgo\s+(?:func|package|mod)\b",
    "Java": r"\bjava\b(?!script)",
    "C++": r"\bc\+\+\b|\bcpp\b",
    "Ruby": r"\bruby\b|\brails\b",
    "PHP": r"\bphp\b|\blaravel\b",
    "Swift": r"\bswift\b|\bswiftui\b",
    "Kotlin": r"\bkotlin\b",
    "SQL": r"\bsql\b|\bpostgres\b|\bmysql\b|\bsqlite\b",
}

_FRAMEWORK_PATTERNS = {
    "React": r"\breact\b(?![\s-]*native)",
    "Next.js": r"\bnext\.?js\b|\bnext\s*js\b",
    "Vue": r"\bvue\.?js\b|\bvue\b",
    "FastAPI": r"\bfastapi\b",
    "Django": r"\bdjango\b",
    "Flask": r"\bflask\b",
    "Express": r"\bexpress\.?js\b|\bexpress\b",
    "Tailwind": r"\btailwind\b",
    "Supabase": r"\bsupabase\b",
    "Prisma": r"\bprisma\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bk8s\b|\bkubernetes\b",
}


def _detect_languages(text: str) -> list[str]:
    found = []
    for lang, pattern in _LANGUAGE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(lang)
    return found


def _detect_frameworks(text: str) -> list[str]:
    found = []
    for fw, pattern in _FRAMEWORK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(fw)
    return found


def _detect_topics(messages: list[str]) -> list[str]:
    """Detect frequently discussed topics via keyword frequency."""
    topic_keywords = {
        "web development": r"\bweb\s*(?:app|dev|site|page)\b|\bfrontend\b|\bbackend\b",
        "machine learning": r"\bml\b|\bmachine\s*learning\b|\bneural\b|\btraining\b",
        "data analysis": r"\bdata\s*(?:analysis|science|viz)\b|\bpandas\b|\bdataframe\b",
        "devops": r"\bdevops\b|\bci/?cd\b|\bdeploy\b|\binfra\b",
        "mobile": r"\bmobile\b|\bios\b|\bandroid\b|\breact\s*native\b|\bflutter\b",
        "api design": r"\bapi\b|\brest\b|\bgraphql\b|\bendpoint\b",
        "databases": r"\bdatabase\b|\bpostgres\b|\bmongo\b|\bredis\b|\bsupabase\b",
        "ai agents": r"\bagent\b|\bmcp\b|\btool\s*use\b|\bfunction\s*call\b",
        "security": r"\bauth\b|\boauth\b|\bjwt\b|\bencrypt\b|\bsecurity\b",
        "testing": r"\btest\b|\bpytest\b|\bjest\b|\bunit\s*test\b",
    }

    counts = Counter()
    all_text = " ".join(messages).lower()
    for topic, pattern in topic_keywords.items():
        matches = len(re.findall(pattern, all_text, re.IGNORECASE))
        if matches >= 2:
            counts[topic] = matches

    return [topic for topic, _ in counts.most_common(8)]


def _detect_style(messages: list[str]) -> dict[str, str]:
    """Detect communication style from message patterns."""
    if not messages:
        return {}

    style = {}

    # Average message length
    avg_len = sum(len(m) for m in messages) / len(messages)
    if avg_len < 50:
        style["brevity"] = "Very concise — short messages"
    elif avg_len < 150:
        style["brevity"] = "Concise — moderate length messages"
    elif avg_len > 500:
        style["brevity"] = "Detailed — long, thorough messages"

    # Language detection (human language)
    french_count = sum(1 for m in messages if re.search(r"\b(je|tu|nous|vous|est|les|des|une|que|pour|dans|avec)\b", m.lower()))
    if french_count > len(messages) * 0.2:
        style["language"] = "Uses French frequently"

    # Code frequency
    code_count = sum(1 for m in messages if "```" in m or "def " in m or "function " in m or "import " in m)
    if code_count > len(messages) * 0.3:
        style["code_heavy"] = "Frequently shares code in conversations"

    return style
