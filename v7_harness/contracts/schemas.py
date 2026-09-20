"""Small standard-library validator for the versioned U10 JSON contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMA_DIR = Path(__file__).with_name("jsonschema")


class SchemaValidationError(ValueError):
    pass


def load_schema(name: str, version: int = 1) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.v{version}.schema.json"
    if not path.is_file():
        raise SchemaValidationError(f"unsupported schema: {name}.v{version}")
    return json.loads(path.read_text(encoding="utf-8"))


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def _validate(value: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        raise SchemaValidationError(f"{path}: expected {expected}")
    if "const" in schema and value != schema["const"]:
        raise SchemaValidationError(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value not in enum")
    if isinstance(value, str):
        if schema.get("minLength", 0) and len(value) < schema["minLength"]:
            raise SchemaValidationError(f"{path}: string too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(f"{path}: string too long")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise SchemaValidationError(f"{path}: string does not match pattern")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value above maximum")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise SchemaValidationError(f"{path}: missing {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(properties)
            if unknown:
                raise SchemaValidationError(f"{path}: unknown fields {sorted(unknown)}")
        for key, child in properties.items():
            if key in value:
                _validate(value[key], child, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]")


def validate_document(name: str, document: dict[str, Any], version: int = 1) -> None:
    """Validate the security-relevant subset used by U10 without dependencies."""
    _validate(document, load_schema(name, version), "$")
    if name == "result":
        effect_state = document.get("effect_state")
        status = document.get("status")
        if effect_state == "UNKNOWN" and document.get("retryable") is not False:
            raise SchemaValidationError("$: UNKNOWN effect must not be retryable")
        if status == "SUCCEEDED" and effect_state in {"UNKNOWN", "INTENDED"}:
            raise SchemaValidationError("$: SUCCEEDED cannot contain an unresolved effect")
    if name == "envelope":
        status = document.get("status")
        if status == "SUCCEEDED" and (document.get("error_class") != "NONE" or document.get("partial") is not False):
            raise SchemaValidationError("$: SUCCEEDED requires error_class NONE and partial false")
        if status in {"ERROR", "PARTIAL"} and document.get("error_class") == "NONE":
            raise SchemaValidationError("$: ERROR/PARTIAL requires a non-NONE error class")
