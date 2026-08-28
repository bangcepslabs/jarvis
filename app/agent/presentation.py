import json
import re

from app.agent.models import PresentationHint

_MARKER = re.compile(r"\s*<!--JARVIS_PRESENTATION\s+(\{.*?\})\s*-->\s*", re.DOTALL)


def parse_presentation_response(content: str | None) -> tuple[str, PresentationHint]:
    """Extract optional one-call presentation metadata without breaking plain text."""
    text = content or ""
    marker = _MARKER.search(text)
    if marker:
        try:
            return _clean(text[:marker.start()] + text[marker.end():]), PresentationHint.model_validate(json.loads(marker.group(1)))
        except (json.JSONDecodeError, TypeError, ValueError):
            return _clean(_MARKER.sub("", text)), PresentationHint()
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, PresentationHint()
    if isinstance(decoded, dict) and "reply" in decoded:
        try:
            return str(decoded["reply"]), PresentationHint.model_validate(decoded.get("presentation_hint") or {})
        except (TypeError, ValueError):
            return str(decoded.get("reply", text)), PresentationHint()
    return text, PresentationHint()


def _clean(value: str) -> str:
    return value.strip()
