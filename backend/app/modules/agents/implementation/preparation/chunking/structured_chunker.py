import json
from typing import Any

from app.modules.agents.implementation.preparation import constants
from app.modules.agents.implementation.preparation.schemas import ChunkWarningCode
from .chunker import DraftChunk
from .tokenizer import bounded_slices, count_tokens


def _path_key(path: str, key: str) -> str:
    return f"{path}.{key}" if key.isidentifier() else f"{path}[{json.dumps(key)}]"


def _render(path: str, value: Any) -> str:
    return f"{path}\n{json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)}"


def chunk_structured(value: Any) -> tuple[list[DraftChunk], list[ChunkWarningCode]]:
    drafts: list[DraftChunk] = []
    warnings: list[ChunkWarningCode] = []

    def visit(item: Any, path: str) -> None:
        text = _render(path, item)
        if count_tokens(text) <= constants.MAX_CHUNK_TOKENS:
            drafts.append(DraftChunk(text, structure_type="STRUCTURED", structured_path=path))
            return
        warnings.append(ChunkWarningCode.STRUCTURED_CONTENT_SPLIT)
        if isinstance(item, dict) and item:
            for key in sorted(item, key=str):
                visit(item[key], _path_key(path, str(key)))
            return
        if isinstance(item, list) and item:
            start = 0
            group: list[Any] = []
            for candidate in item:
                trial = [*group, candidate]
                if group and count_tokens(_render(f"{path}[{start}:{start + len(trial)}]", trial)) > constants.MAX_CHUNK_TOKENS:
                    end = start + len(group)
                    drafts.append(DraftChunk(_render(f"{path}[{start}:{end}]", group), structure_type="ARRAY", structured_path=f"{path}[{start}:{end}]"))
                    start = end
                    group = [candidate]
                else:
                    group = trial
            if group:
                end = start + len(group)
                group_path = f"{path}[{start}:{end}]"
                group_text = _render(group_path, group)
                for part in bounded_slices(group_text, constants.MAX_CHUNK_TOKENS, constants.OVERLAP_TOKENS):
                    drafts.append(DraftChunk(part, structure_type="ARRAY", structured_path=group_path, structural_warning=ChunkWarningCode.CHUNKING_FALLBACK_USED if count_tokens(group_text) > constants.MAX_CHUNK_TOKENS else None))
            return
        for part in bounded_slices(text, constants.MAX_CHUNK_TOKENS, constants.OVERLAP_TOKENS):
            drafts.append(DraftChunk(part, structure_type="STRUCTURED", structured_path=path, structural_warning=ChunkWarningCode.CHUNKING_FALLBACK_USED))
            warnings.append(ChunkWarningCode.CHUNKING_FALLBACK_USED)

    if isinstance(value, dict):
        if not value:
            visit(value, "$")
        else:
            for key in sorted(value, key=str):
                visit(value[key], _path_key("$", str(key)))
    elif isinstance(value, list) and value:
        visit(value, "$")
    else:
        visit(value, "$")
    return drafts, list(dict.fromkeys(warnings))
