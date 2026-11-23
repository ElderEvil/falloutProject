"""Ratchet: every documented operation must declare a usable response schema.

Reads the generated OpenAPI document (FastAPI infers schemas from return annotations, so
counting ``response_model`` kwargs measures style, not the wire contract) and requires each
2xx response to be ``structured``, ``legitimate`` (204/205, or a non-JSON media type) or
``unresolved``. A new unresolved response fails the suite; fixing a listed operation fails
it too, because the baseline entry becomes stale.
"""

from typing import Any

from main import app

#: Every operation method in the OpenAPI Path Item Object (not ``parameters``,
#: ``summary``, ``description``, ``servers``, or ``$ref``, which are metadata).
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

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

#: Shrink-only: entries are deleted as operations gain typed responses, never added.
#: An operation with genuinely no JSON schema belongs in ``EXEMPT`` with a reason.
UNRESOLVED_BASELINE: frozenset[str] = frozenset()

PRIMITIVE_TYPES = frozenset({"string", "integer", "number", "boolean"})
JSON_MEDIA_TYPE = "application/json"
#: Statuses that forbid a response body outright, so omitting ``content`` is the
#: correct contract rather than an undeclared payload.
BODYLESS_STATUSES = frozenset({"204", "205"})
REF_PREFIX = "#/components/schemas/"


def _resolve_component(ref: str, document: dict[str, Any] | None) -> tuple[str, dict[str, Any]] | None:
    """Name and schema for a local component ``$ref``; None when it cannot be resolved.

    An unresolvable ref must not count as typed: a dangling reference hides the same
    unconstrained payload a bare ``{}`` does, and passes the guard silently.
    """
    if document is None or not ref.startswith(REF_PREFIX):
        return None
    name = ref[len(REF_PREFIX) :]
    schemas = (document.get("components") or {}).get("schemas") or {}
    schema = schemas.get(name)
    return (name, schema) if isinstance(schema, dict) else None


def _is_typed_schema(
    schema: Any,
    *,
    allow_null: bool = False,
    document: dict[str, Any] | None = None,
    _seen: frozenset[str] = frozenset(),
) -> bool:
    """Whether a JSON schema fragment constrains its payload to a known shape."""
    if not isinstance(schema, dict):
        return False
    if "$ref" in schema:
        resolved = _resolve_component(schema["$ref"], document)
        if resolved is None:
            return False
        name, target = resolved
        # An alias cycle (A -> B -> A) defines no shape at all, so it is not a contract.
        if name in _seen:
            return False
        return _is_typed_schema(target, allow_null=allow_null, document=document, _seen=_seen | {name})
    for combinator in ("anyOf", "oneOf"):
        members = schema.get(combinator)
        if (
            isinstance(members, list)
            and members
            and all(_is_typed_schema(member, allow_null=True, document=document, _seen=_seen) for member in members)
        ):
            return True
    schema_type = schema.get("type")
    if schema_type == "object":
        return bool(schema.get("properties"))
    if schema_type == "array":
        # ``items`` must itself be typed: an array of unconstrained objects is
        # no more a contract than a bare ``{"type": "array"}``. Nullable elements
        # are allowed so arrays of ``anyOf``/``oneOf`` with ``null`` still pass.
        return _is_typed_schema(schema.get("items"), allow_null=True, document=document, _seen=_seen)
    if schema_type in PRIMITIVE_TYPES:
        return True
    return allow_null and schema_type == "null"


def _classify_response(response: dict[str, Any], status: str | int = "200", *, document=None) -> str:
    """Classify one response object; ``status`` decides whether omitting ``content`` is honest."""
    content = response.get("content") or {}
    if not content:
        return LEGITIMATE if str(status) in BODYLESS_STATUSES else UNRESOLVED
    if JSON_MEDIA_TYPE not in content:
        return LEGITIMATE
    media = content.get(JSON_MEDIA_TYPE) or {}
    schema = media.get("schema")
    if not schema:
        return UNRESOLVED
    return STRUCTURED if _is_typed_schema(schema, document=document) else UNRESOLVED


def _classify_operation(operation: dict[str, Any], document: dict[str, Any] | None = None) -> str:
    """Worst 2xx classification for an operation; no 2xx at all is unresolved."""
    classifications = {
        _classify_response(response, status, document=document)
        for status, response in (operation.get("responses") or {}).items()
        if str(status).startswith("2")
    }
    if not classifications:
        return UNRESOLVED
    if UNRESOLVED in classifications:
        return UNRESOLVED
    if STRUCTURED in classifications:
        return STRUCTURED
    return LEGITIMATE


def _classify_operations(document: dict[str, Any] | None = None) -> dict[str, str]:
    """Every documented operation keyed by "METHOD path", refs resolved inside ``document``."""
    document = app.openapi() if document is None else document
    return {
        f"{method.upper()} {path}": _classify_operation(operation, document)
        for path, path_item in document["paths"].items()
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
        "response model (a Pydantic model with declared fields, or a $ref to one). "
        "UNRESOLVED_BASELINE is shrink-only and must not be extended. If an "
        "operation genuinely cannot declare a JSON schema, add it to EXEMPT with a "
        "written reason instead:\n  " + "\n  ".join(new)
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

    document = {
        "components": {
            "schemas": {"X": {"type": "object", "properties": {"id": {"type": "string"}}}},
        }
    }
    looping = {
        "components": {
            "schemas": {
                "LoopA": {"$ref": "#/components/schemas/LoopB"},
                "LoopB": {"$ref": "#/components/schemas/LoopA"},
            },
        }
    }

    # Unconstrained or absent schemas must be rejected.
    assert _classify_response(response({})) == UNRESOLVED
    assert _classify_response(response()) == UNRESOLVED
    assert _classify_response(response({"type": "object", "additionalProperties": True})) == UNRESOLVED
    assert _classify_response(response({"type": "object"})) == UNRESOLVED
    assert _classify_response(response({"type": "array"})) == UNRESOLVED
    # An array whose elements are unconstrained is no contract at all.
    assert (
        _classify_response(response({"type": "array", "items": {"type": "object", "additionalProperties": True}}))
        == UNRESOLVED
    )
    assert _classify_response(response({"type": "array", "items": {"type": "object"}})) == UNRESOLVED
    assert _classify_response(response({"type": "array", "items": {}})) == UNRESOLVED

    # Typed schemas and legitimate non-JSON payloads must be accepted.
    assert _classify_response(response({"$ref": "#/components/schemas/X"}), document=document) == STRUCTURED
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
            ),
            document=document,
        )
        == STRUCTURED
    )
    assert _classify_response(response({"type": "string"})) == STRUCTURED
    # Arrays stay valid when their elements are typed, including null elements.
    assert _classify_response(response({"type": "array", "items": {"type": "string"}})) == STRUCTURED
    assert (
        _classify_response(response({"type": "array", "items": {"$ref": "#/components/schemas/X"}}), document=document)
        == STRUCTURED
    )
    # A ref the document cannot resolve (or that only aliases itself) is not a contract.
    assert _classify_response(response({"$ref": "#/components/schemas/Missing"}), document=document) == UNRESOLVED
    assert _classify_response(response({"$ref": "#/components/schemas/X"})) == UNRESOLVED
    assert (
        _classify_response(response({"$ref": "https://example.com/schemas.json#/X"}), document=document) == UNRESOLVED
    )
    assert _classify_response(response({"$ref": "#/components/schemas/LoopA"}), document=looping) == UNRESOLVED
    assert (
        _classify_response(
            response({"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}}}})
        )
        == STRUCTURED
    )
    assert (
        _classify_response(
            response(
                {
                    "type": "array",
                    "items": {"anyOf": [{"$ref": "#/components/schemas/X"}, {"type": "null"}]},
                }
            ),
            document=document,
        )
        == STRUCTURED
    )
    assert _classify_response(response(media_type="text/event-stream")) == LEGITIMATE
    assert _classify_response(response(media_type="text/html")) == LEGITIMATE

    # A 2xx that may carry a body but declares no content at all is unresolved: an endpoint
    # returning an undeclared JSON body must never pass by omission.
    assert _classify_response({"description": "no body"}) == UNRESOLVED
    assert _classify_response({"content": {}}) == UNRESOLVED
    assert _classify_response({}, status=200) == UNRESOLVED
    assert _classify_response({}, status=201) == UNRESOLVED
    # Statuses that forbid a body stay legitimate, and declared content still wins when present.
    assert _classify_response({"description": "no body"}, status=204) == LEGITIMATE
    assert _classify_response({"content": {}}, status=205) == LEGITIMATE
    assert _classify_response(response({"type": "string"}), status=204) == STRUCTURED


def test_ref_to_unconstrained_component_is_unresolved() -> None:
    """A $ref is a contract only when the component it names is one."""

    def operation(schema: Any) -> dict[str, Any]:
        return {"responses": {"200": {"content": {JSON_MEDIA_TYPE: {"schema": schema}}}}}

    document = {
        "components": {
            "schemas": {
                # What ``RootModel[dict[str, Any]]`` (or a bare ``dict`` annotation) generates.
                "Anything": {"type": "object", "additionalProperties": True},
                "Typed": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            }
        },
        "paths": {
            "/anything": {"get": operation({"$ref": "#/components/schemas/Anything"})},
            "/typed": {"get": operation({"$ref": "#/components/schemas/Typed"})},
            "/dangling": {"get": operation({"$ref": "#/components/schemas/Missing"})},
        },
    }

    assert _classify_operations(document) == {
        "GET /anything": UNRESOLVED,
        "GET /typed": STRUCTURED,
        "GET /dangling": UNRESOLVED,
    }
