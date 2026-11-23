"""Ratchet: every documented operation must declare a usable response schema.

FastAPI infers the response schema from the return annotation, so counting
``response_model`` kwargs measures style, not wire contract. This guard reads the
generated OpenAPI document instead.

Each 2xx response must be one of:

* ``structured`` — an ``application/json`` schema naming a ``$ref``, an object
  with properties, a typed array, a primitive, or a union of those;
* ``legitimate`` — no body at all (204) or a non-JSON media type such as
  ``text/event-stream`` or ``text/html``;
* ``unresolved`` — JSON schema absent, empty, or unconstrained (an object with
  neither properties nor ``$ref``, or ``additionalProperties: true``).

A new operation with an unresolved response fails the suite. Fixing a listed
operation fails it too, because the baseline entry becomes stale and must be
deleted in the same change.
"""

from typing import Any

from main import app

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

STRUCTURED = "structured"
LEGITIMATE = "legitimate"
UNRESOLVED = "unresolved"

#: Operations that are legitimately outside the JSON contract, keyed by
#: "METHOD path" so an untyped method added to an exempt path still fails.
EXEMPT: dict[str, str] = {
    "GET /healthcheck": "liveness probe; body is an untyped JSON envelope",
    "GET /readiness": "readiness probe; body is an untyped JSON envelope",
    "GET /api/v1/auth/oauth/{provider}/authorize": ("starts the OAuth redirect; provider-specific JSON envelope"),
    "GET /api/v1/auth/oauth/{provider}/callback": ("provider callback; provider-specific JSON envelope"),
    "GET /api/v1/stream/notifications": "server-sent events; text/event-stream",
    "GET /api/v1/stream/game/{vault_id}/ticks": "server-sent events; text/event-stream",
    "GET /api/v1/stream/exploration/{vault_id}": "server-sent events; text/event-stream",
    "GET /api/v1/stream/incidents/{vault_id}": "server-sent events; text/event-stream",
}

#: Measured debt at 8fa8f6b27. Shrink this; never grow it without a reason.
UNRESOLVED_BASELINE: frozenset[str] = frozenset(
    {
        "GET /api/v1/game/vaults/{vault_id}/game-state",
        "POST /api/v1/game/vaults/{vault_id}/tick",
        "POST /api/v1/junk/{junk_id}/sell/",
        "POST /api/v1/objectives/{vault_id}/{objective_id}/progress",
        "POST /api/v1/objectives/{vault_id}/assign-random",
        "POST /api/v1/outfits/{outfit_id}/sell/",
        "POST /api/v1/outfits/{outfit_id}/unequip/",
        "POST /api/v1/pets/{pet_id}/unequip/",
        "POST /api/v1/quests/{vault_id}/{quest_id}/assign",
        "POST /api/v1/vaults/update_resources",
        "POST /api/v1/weapons/{weapon_id}/sell/",
        "POST /api/v1/weapons/{weapon_id}/unequip/",
    }
)

PRIMITIVE_TYPES = frozenset({"string", "integer", "number", "boolean"})
JSON_MEDIA_TYPE = "application/json"


def _is_typed_schema(schema: Any, *, allow_null: bool = False) -> bool:
    """Whether a JSON schema fragment constrains its payload to a known shape."""
    if not isinstance(schema, dict):
        return False
    if "$ref" in schema:
        return True
    for combinator in ("anyOf", "oneOf"):
        members = schema.get(combinator)
        if (
            isinstance(members, list)
            and members
            and all(_is_typed_schema(member, allow_null=True) for member in members)
        ):
            return True
    schema_type = schema.get("type")
    if schema_type == "object":
        return bool(schema.get("properties"))
    if schema_type == "array":
        return bool(schema.get("items"))
    if schema_type in PRIMITIVE_TYPES:
        return True
    return allow_null and schema_type == "null"


def _classify_response(response: dict[str, Any]) -> str:
    """Classify one response object as structured, legitimate, or unresolved."""
    content = response.get("content") or {}
    if not content:
        return LEGITIMATE
    if JSON_MEDIA_TYPE not in content:
        return LEGITIMATE
    media = content.get(JSON_MEDIA_TYPE) or {}
    schema = media.get("schema")
    if not schema:
        return UNRESOLVED
    return STRUCTURED if _is_typed_schema(schema) else UNRESOLVED


def _classify_operation(operation: dict[str, Any]) -> str:
    """Worst 2xx classification for an operation; no 2xx at all is unresolved."""
    successes = [
        response for status, response in (operation.get("responses") or {}).items() if str(status).startswith("2")
    ]
    if not successes:
        return UNRESOLVED
    classifications = {_classify_response(response) for response in successes}
    if UNRESOLVED in classifications:
        return UNRESOLVED
    if STRUCTURED in classifications:
        return STRUCTURED
    return LEGITIMATE


def _classify_operations() -> dict[str, str]:
    """Every documented operation keyed by "METHOD path"."""
    return {
        f"{method.upper()} {path}": _classify_operation(operation)
        for path, path_item in app.openapi()["paths"].items()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    }


def _unresolved_operations() -> set[str]:
    return {
        key
        for key, classification in _classify_operations().items()
        if classification == UNRESOLVED and key not in EXEMPT
    }


def test_operation_tally_is_not_vacuous() -> None:
    operations = _classify_operations()
    assert len(operations) > 250, (
        f"openapi documents only {len(operations)} operations; the guard would pass without seeing the API"
    )


def test_no_new_unresolved_responses() -> None:
    new = sorted(_unresolved_operations() - UNRESOLVED_BASELINE)
    assert not new, (
        "Operations whose 2xx response has no usable JSON schema. Return a typed "
        "response model, or add the operation to UNRESOLVED_BASELINE with a reason:\n  " + "\n  ".join(new)
    )


def test_unresolved_baseline_has_no_stale_entries() -> None:
    stale = sorted(UNRESOLVED_BASELINE - _unresolved_operations())
    assert not stale, (
        "UNRESOLVED_BASELINE lists operations that are already resolved or gone. "
        "Delete these entries:\n  " + "\n  ".join(stale)
    )


def test_exempt_operations_exist_and_stay_untyped() -> None:
    classifications = _classify_operations()
    missing = sorted(key for key in EXEMPT if key not in classifications)
    assert not missing, f"EXEMPT lists operations that no longer exist: {missing}"
    typed = sorted(key for key in EXEMPT if classifications[key] == STRUCTURED)
    assert not typed, f"EXEMPT operations now declare a structured schema; drop the exemption: {typed}"


def test_classifier_self_test() -> None:
    """Synthetic fragments prove the predicate bites without touching app routes."""

    def response(schema: Any = None, *, media_type: str = JSON_MEDIA_TYPE) -> dict[str, Any]:
        media: dict[str, Any] = {}
        if schema is not None:
            media["schema"] = schema
        return {"content": {media_type: media}}

    # Unconstrained or absent schemas must be rejected.
    assert _classify_response(response({})) == UNRESOLVED
    assert _classify_response(response()) == UNRESOLVED
    assert _classify_response({"content": {}}) == LEGITIMATE
    assert _classify_response(response({"type": "object", "additionalProperties": True})) == UNRESOLVED
    assert _classify_response(response({"type": "object"})) == UNRESOLVED
    assert _classify_response(response({"type": "array"})) == UNRESOLVED

    # Typed schemas and legitimate non-JSON payloads must be accepted.
    assert _classify_response(response({"$ref": "#/components/schemas/X"})) == STRUCTURED
    assert _classify_response(response({"type": "object", "properties": {"id": {"type": "string"}}})) == STRUCTURED
    assert (
        _classify_response(
            response(
                {
                    "anyOf": [
                        {"$ref": "#/components/schemas/X"},
                        {"type": "null"},
                    ]
                }
            )
        )
        == STRUCTURED
    )
    assert _classify_response(response({"type": "string"})) == STRUCTURED
    assert _classify_response({"description": "no body"}) == LEGITIMATE
    assert _classify_response(response(media_type="text/event-stream")) == LEGITIMATE
    assert _classify_response(response(media_type="text/html")) == LEGITIMATE
