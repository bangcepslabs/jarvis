import json
import re

from app.agent.models import PresentationHint

_MARKER = re.compile(r"\s*<!--JARVIS_PRESENTATION\s+(\{.*?\})\s*-->\s*", re.DOTALL)
_REFUSAL_MARKERS = (
    "\uC5ED\uD560\uADF9",
    "\uC131\uC801",
    "\uD2B9\uC815 \uC18C\uB9AC",
    "\uC74C\uC131 \uAE30\uB2A5",
    "\uC74C\uC131 \uCF58\uD150\uCE20",
)
_REFUSAL_WORDS = (
    "\uCC38\uC5EC\uD558\uC9C0 \uC54A",
    "\uC9C0\uC6D0\uD558\uC9C0 \uC54A",
    "\uD560 \uC218 \uC5C6",
    "\uBABB \uD574",
    "\uC548 \uB3FC",
    "cannot",
    "unable",
)
_SERVICE_CLOSINGS = (
    "\uB2E4\uB978 \uB3C4\uC6C0",
    "\uB9D0\uC500\uD574 \uC8FC",
    "\uB9D0\uC500\uD574\uC8FC",
    "\uB3C4\uC640\uB4DC\uB9B4\uAE4C",
    "how else can i help",
)

_SYNTHETIC_FAILURE_RESPONSES = frozenset({
    "i could not generate a response.",
    "\uc751\ub2f5\uc744 \ub9cc\ub4e4\uc9c0 \ubabb\ud588\uc5b4\uc694. \ub2e4\uc2dc \ub9d0\uc500\ud574 \uc8fc\uc138\uc694.",
    "the ai service is currently unavailable.",
    "\ud604\uc7ac ai \uc11c\ube44\uc2a4\ub97c \uc0ac\uc6a9\ud560 \uc218 \uc5c6\uc5b4\uc694.",
    "the requested information could not be retrieved.",
    "\uc694\uccad\ud55c \uc815\ubcf4\ub97c \uac00\uc838\uc624\uc9c0 \ubabb\ud588\uc5b4\uc694.",
    "tool result received.",
    "\ub3c4\uad6c \uacb0\uacfc\ub97c \ud655\uc778\ud588\uc5b4\uc694.",
    "\uc751\ub2f5\uc774 \ube44\uc5c8\uc5b4. \ud55c \ubc88\ub9cc \ub354 \ub9d0\ud574\uc918.",
})


def parse_presentation_response(content: str | None) -> tuple[str, PresentationHint]:
    """Extract optional one-call presentation metadata without breaking plain text."""
    text = content or ""
    marker = _MARKER.search(text)
    if marker:
        try:
            return _clean(text[:marker.start()] + text[marker.end():]), _safe_hint(json.loads(marker.group(1)))
        except (json.JSONDecodeError, TypeError, ValueError):
            return _clean(_MARKER.sub("", text)), PresentationHint()
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, PresentationHint()
    if isinstance(decoded, dict) and "reply" in decoded:
        try:
            return str(decoded["reply"]), _safe_hint(decoded.get("presentation_hint") or {})
        except (TypeError, ValueError):
            return str(decoded.get("reply", text)), PresentationHint()
    return text, PresentationHint()


def has_usable_response_text(content: str | None) -> bool:
    """Return whether an LLM response contains user-facing text.

    A presentation marker is metadata, not a reply.  Keeping this check next
    to the marker parser prevents marker-only responses from entering the
    normal conversation history or the character presentation pass.
    """
    reply, _ = parse_presentation_response(content)
    return bool(reply.strip())


def is_known_synthetic_failure_text(text: str | None) -> bool:
    """Recognize only the agent's own fixed fallback/sentinel replies."""
    normalized = " ".join((text or "").casefold().split())
    return normalized in _SYNTHETIC_FAILURE_RESPONSES or normalized.startswith(
        "the ai service is temporarily rate limited."
    )


def invalid_generated_response_reason(content: str | None) -> str | None:
    """Return a narrow invalidity reason for a main LLM response."""
    reply, _ = parse_presentation_response(content)
    if not reply.strip():
        return "marker_only" if _MARKER.search(content or "") else "empty"
    if is_known_synthetic_failure_text(reply):
        return "generated_failure_fallback"
    return None


def present_refusal_response(user_message: str, response: str) -> str:
    """Keep an explicit refusal boundary while removing canned service tone.

    This is presentation-only. It deliberately requires a refusal, a
    capability/topic marker, and a service-style closing before changing text.
    Tool authorization and safety decisions happen elsewhere.
    """

    normalized = " ".join((response or "").casefold().split())
    if not normalized:
        return response
    if not any(marker.casefold() in normalized for marker in _REFUSAL_MARKERS):
        return response
    if not any(marker.casefold() in normalized for marker in _REFUSAL_WORDS):
        return response
    if not any(marker.casefold() in normalized for marker in _SERVICE_CLOSINGS):
        return response
    if re.search(r"[\uAC00-\uD7A3]", user_message):
        return "거기부터는 너무 노골적이잖아 ㅋㅋ 그 정도까진 안 가."
    return "I can't do that right now."


def _clean(value: str) -> str:
    return value.strip()


def _safe_hint(value: object) -> PresentationHint:
    if not isinstance(value, dict):
        return PresentationHint()
    defaults = PresentationHint()
    fields = {}
    for name in ("emotion", "intensity", "motion_intent", "attitude", "reaction", "duration"):
        try:
            fields[name] = PresentationHint.model_validate({name: value.get(name, getattr(defaults, name))}).__getattribute__(name)
        except (TypeError, ValueError):
            fields[name] = getattr(defaults, name)
    return PresentationHint(**fields)
