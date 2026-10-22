import json
import re

import yaml

from ..schemas import (
    CanonicalSourceRef, CanonicalStatus, DatabaseEntityItem, DatabaseFieldItem,
    DatabaseSchemaData,
)
from .common import ExtractionOutcome, unresolved


def extract(text: str, source: CanonicalSourceRef) -> ExtractionOutcome:
    entities = _sql_entities(text, source)
    if not entities:
        entities = _structured_entities(text, source)
    if not entities:
        entities = _markdown_entities(text, source)
    if not entities:
        return ExtractionOutcome(DatabaseSchemaData(entities=[]), CanonicalStatus.UNRESOLVED,
                                 unresolved("NO_EXPLICIT_DATABASE_STRUCTURE", source))
    partial = any(not entity.fields for entity in entities)
    return ExtractionOutcome(
        DatabaseSchemaData(entities=entities),
        CanonicalStatus.PARTIAL if partial else CanonicalStatus.COMPLETE,
        unresolved("DATABASE_FIELDS_NOT_EXPLICIT", source) if partial else [],
    )


def _sql_entities(text, source):
    entities = []
    pattern = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?([A-Za-z_]\w*)[\"`\]]?\s*\(", re.I)
    for match in pattern.finditer(text):
        name = match.group(1)
        body, depth = [], 1
        for character in text[match.end():]:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    break
            body.append(character)
        if depth:
            continue
        body = "".join(body)
        fields = []
        table_primary = set(re.findall(r"PRIMARY\s+KEY\s*\(([^)]+)\)", body, re.I))
        primary_names = {value.strip(" `\"[]") for group in table_primary for value in group.split(",")}
        foreign = {
            field.strip(" `\"[]"): target
            for field, target in re.findall(
                r"FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+([A-Za-z_]\w*(?:\s*\([^)]+\))?)",
                body, re.I,
            )
        }
        for definition in _split_columns(body):
            if re.match(r"^(?:PRIMARY|FOREIGN|UNIQUE|CONSTRAINT|CHECK)\b", definition, re.I):
                continue
            column = re.match(r"^[\"`\[]?([A-Za-z_]\w*)[\"`\]]?\s+([A-Za-z]+(?:\s*\([^)]*\))?)\s*(.*)$", definition, re.I)
            if not column:
                continue
            field_name, field_type, modifiers = column.group(1), column.group(2).upper(), column.group(3)
            inline_fk = re.search(r"REFERENCES\s+([A-Za-z_]\w*\s*\([^)]+\))", modifiers, re.I)
            nullable = False if re.search(r"NOT\s+NULL", modifiers, re.I) else (True if re.search(r"\bNULL\b", modifiers, re.I) else None)
            fields.append(DatabaseFieldItem(
                name=field_name, type=field_type, nullable=nullable,
                primary_key=bool(re.search(r"PRIMARY\s+KEY", modifiers, re.I) or field_name in primary_names),
                foreign_key=inline_fk.group(1) if inline_fk else foreign.get(field_name),
            ))
        entities.append(DatabaseEntityItem(name=name, fields=_dedupe_fields(fields), source_refs=[source]))
    return entities


def _structured_entities(text, source):
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            value = yaml.safe_load(text)
        except (TypeError, ValueError, yaml.YAMLError):
            return []
    tables = value.get("tables", value) if isinstance(value, dict) else None
    if not isinstance(tables, dict):
        return []
    entities = []
    for name, definition in tables.items():
        if not isinstance(definition, (dict, list)):
            continue
        raw_fields = definition.get("fields", definition.get("columns", definition)) if isinstance(definition, dict) else definition
        fields = []
        if isinstance(raw_fields, dict):
            for field_name, details in raw_fields.items():
                details = details if isinstance(details, dict) else {"type": details}
                fields.append(DatabaseFieldItem(
                    name=str(field_name), type=str(details.get("type")) if details.get("type") is not None else None,
                    nullable=details.get("nullable") if isinstance(details.get("nullable"), bool) else None,
                    primary_key=bool(details.get("primary_key", False)),
                    foreign_key=str(details.get("foreign_key")) if details.get("foreign_key") else None,
                ))
        elif isinstance(raw_fields, list):
            for details in raw_fields:
                if isinstance(details, dict) and details.get("name"):
                    fields.append(DatabaseFieldItem(
                        name=str(details["name"]), type=str(details.get("type")) if details.get("type") else None,
                        nullable=details.get("nullable") if isinstance(details.get("nullable"), bool) else None,
                        primary_key=bool(details.get("primary_key", False)),
                        foreign_key=str(details.get("foreign_key")) if details.get("foreign_key") else None,
                    ))
        entities.append(DatabaseEntityItem(name=str(name), fields=_dedupe_fields(fields), source_refs=[source]))
    return entities


def _markdown_entities(text, source):
    table_name = re.search(r"(?:Table|Entity)\s*[:#-]\s*([A-Za-z_]\w*)", text, re.I)
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    if not table_name or len(lines) < 3:
        return []
    headers = [cell.strip().casefold() for cell in lines[0].strip("|").split("|")]
    if "name" not in headers and "field" not in headers and "column" not in headers:
        return []
    name_index = next((headers.index(key) for key in ("name", "field", "column") if key in headers), 0)
    type_index = headers.index("type") if "type" in headers else None
    fields = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) <= name_index or not cells[name_index]:
            continue
        fields.append(DatabaseFieldItem(
            name=cells[name_index], type=cells[type_index] if type_index is not None and len(cells) > type_index else None,
            nullable=None, primary_key=any("primary" in cell.casefold() for cell in cells),
        ))
    return [DatabaseEntityItem(name=table_name.group(1), fields=_dedupe_fields(fields), source_refs=[source])]


def _split_columns(body):
    values, current, depth = [], [], 0
    for character in body:
        depth += character == "("
        depth -= character == ")"
        if character == "," and depth == 0:
            values.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if current:
        values.append("".join(current).strip())
    return values


def _dedupe_fields(fields):
    result = {}
    for field in fields:
        result.setdefault((field.name.casefold(), field.type or "", field.nullable,
                           field.primary_key, field.foreign_key or ""), field)
    return list(result.values())
