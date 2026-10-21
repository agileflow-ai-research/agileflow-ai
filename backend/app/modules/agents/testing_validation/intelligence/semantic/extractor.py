import hashlib
import json
import re
from datetime import datetime

from pydantic import ValidationError

from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TestingIntelligenceLabel,
)

from . import constants
from .prompt import build_semantic_prompt
from .schemas import (
    SemanticFact,
    SemanticFactCandidate,
    SemanticGenerationMetadata,
    SemanticResultStatus,
    SemanticWarning,
    TestingSemanticResult,
)


class SemanticExtractionFailedError(RuntimeError):
    pass


def generation_configuration_fingerprint():
    payload = {
        "schema": constants.SEMANTIC_SCHEMA_VERSION,
        "stage": constants.SEMANTIC_STAGE_VERSION,
        "prompt": constants.SEMANTIC_PROMPT_VERSION,
        "grounding": constants.SEMANTIC_GROUNDING_VERSION,
        "policy": constants.SEMANTIC_GENERATION_POLICY_VERSION,
        "model": constants.SEMANTIC_MODEL_ID,
        "revision": constants.SEMANTIC_MODEL_REVISION,
        "max_input": constants.MAX_SEMANTIC_INPUT_TOKENS,
        "max_new": constants.MAX_SEMANTIC_NEW_TOKENS,
        "do_sample": constants.DO_SAMPLE,
        "attempts": constants.MAX_SEMANTIC_ATTEMPTS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_one_object(raw):
    candidate = raw.strip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        raise ValueError("SEMANTIC_INVALID_JSON")
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("SEMANTIC_INVALID_JSON") from exc
    if not isinstance(value, dict) or set(value) != {"facts"} or not isinstance(value["facts"], list):
        raise ValueError("SEMANTIC_SCHEMA_VALIDATION_FAILED")
    return value["facts"]


def _ground(candidate, chunk_text, accepted_labels):
    if (not set(candidate.related_labels).issubset(set(accepted_labels))
            or TestingIntelligenceLabel.NON_TESTABLE_CONTEXT in candidate.related_labels):
        raise ValueError("UNSUPPORTED_RELATED_LABEL")
    quote = candidate.evidence_quote
    start, end = candidate.evidence_start, candidate.evidence_end
    if start is not None:
        if end > len(chunk_text) or chunk_text[start:end] != quote:
            raise ValueError("SEMANTIC_GROUNDING_FAILED")
    else:
        occurrences = [match.start() for match in re.finditer(re.escape(quote), chunk_text)]
        if len(occurrences) != 1:
            raise ValueError("SEMANTIC_GROUNDING_FAILED")
        start = occurrences[0]
        end = start + len(quote)
    payload = candidate.model_dump()
    payload["evidence_start"] = start
    payload["evidence_end"] = end
    semantic = candidate.model_dump(exclude={
        "fact_type", "related_labels", "evidence_quote", "evidence_start", "evidence_end"
    })
    quote_folded = quote.casefold()
    for key, value in semantic.items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item in (None, ""):
                continue
            token = str(item).casefold()
            if isinstance(item, bool):
                token = str(item).lower()
            if token not in quote_folded:
                raise ValueError(f"UNSUPPORTED_SEMANTIC_VALUE_{key.upper()}")
    return payload


def _fact_id(chunk_id, payload):
    identity = {
        "chunk_id": chunk_id,
        "schema": constants.SEMANTIC_SCHEMA_VERSION,
        "prompt": constants.SEMANTIC_PROMPT_VERSION,
        "fact": payload,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return "A4FACT-" + hashlib.sha256(canonical.encode()).hexdigest()[:32]


def _result_id(chunk, hybrid_result_id, accepted_labels, effective_result_id=None):
    payload = {
        "chunk": chunk.chunk_id,
        "text": chunk.text_sha256,
        "hybrid": hybrid_result_id,
        "effective": effective_result_id,
        "labels": [label.value for label in accepted_labels],
        "config": generation_configuration_fingerprint(),
    }
    return "A4SEM-" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:32]


def extract_semantic_result(*, chunk, chunk_reference, hybrid_result,
                            accepted_labels, runtime, processed_at: datetime,
                            effective_result_id=None, context_fingerprint=None):
    feedback = None
    total_ms = total_output = 0
    last_input = 0
    device = None
    for attempt in range(1, constants.MAX_SEMANTIC_ATTEMPTS + 1):
        prompt = build_semantic_prompt(
            chunk.text, accepted_labels, correction_feedback=feedback
        )
        output = runtime.generate(prompt)
        total_ms += output.generation_duration_ms
        total_output += output.output_token_count
        last_input = output.input_token_count
        device = output.device
        try:
            raw_candidates = parse_one_object(output.text)
        except ValueError as exc:
            feedback = str(exc)
            continue
        if not raw_candidates:
            return _result(
                chunk_reference, hybrid_result, accepted_labels,
                SemanticResultStatus.EMPTY, [], 0, [], attempt,
                last_input, total_output, total_ms, device, processed_at,
                effective_result_id, context_fingerprint,
            )
        facts = []
        warnings = []
        for index, raw in enumerate(raw_candidates):
            try:
                candidate = SemanticFactCandidate.model_validate(raw)
                grounded = _ground(candidate, chunk.text, accepted_labels)
                facts.append(SemanticFact(
                    fact_id=_fact_id(chunk.chunk_id, grounded), **grounded
                ))
            except (ValidationError, ValueError) as exc:
                warnings.append(SemanticWarning(
                    code="SEMANTIC_CANDIDATE_REJECTED",
                    message=str(exc).splitlines()[0][:500],
                    candidate_index=index,
                ))
        unique = {fact.fact_id: fact for fact in facts}
        facts = sorted(
            unique.values(),
            key=lambda fact: (fact.evidence_start, fact.fact_type.value, fact.fact_id),
        )
        if facts:
            status = (
                SemanticResultStatus.SUCCESS_WITH_WARNINGS
                if warnings else SemanticResultStatus.SUCCESS
            )
            return _result(
                chunk_reference, hybrid_result, accepted_labels, status, facts,
                len(warnings), warnings, attempt,
                last_input, total_output, total_ms, device, processed_at,
                effective_result_id, context_fingerprint,
            )
        feedback = "ALL_CANDIDATES_INVALID:" + ";".join(
            warning.message for warning in warnings[:3]
        )
    raise SemanticExtractionFailedError("SEMANTIC_MODEL_OUTPUT_INVALID")


def disposition_result(*, chunk_reference, hybrid_result, accepted_labels,
                       status, processed_at, effective_result_id=None,
                       context_fingerprint=None):
    return _result(
        chunk_reference, hybrid_result, accepted_labels, status, [], 0, [], 0,
        0, 0, 0, None, processed_at, effective_result_id, context_fingerprint,
    )


def _result(chunk_reference, hybrid, labels, status, facts, rejected, warnings,
            attempts, input_tokens, output_tokens, duration, device, at,
            effective_result_id=None, context_fingerprint=None):
    return TestingSemanticResult(
        semantic_result_id=_result_id(
            chunk_reference, hybrid.result_id, labels, effective_result_id
        ),
        chunk=chunk_reference,
        taxonomy_version="T1", hybrid_policy_version="H1",
        hybrid_result_id=hybrid.result_id, accepted_labels=labels,
        effective_result_id=effective_result_id,
        classification_context_fingerprint=context_fingerprint,
        semantic_schema_version=constants.SEMANTIC_SCHEMA_VERSION,
        semantic_stage_version=constants.SEMANTIC_STAGE_VERSION,
        prompt_version=constants.SEMANTIC_PROMPT_VERSION,
        grounding_version=constants.SEMANTIC_GROUNDING_VERSION,
        model_id=constants.SEMANTIC_MODEL_ID,
        model_revision=constants.SEMANTIC_MODEL_REVISION,
        generation_policy_version=constants.SEMANTIC_GENERATION_POLICY_VERSION,
        status=status, facts=facts, rejected_candidate_count=rejected,
        warnings=warnings,
        generation=SemanticGenerationMetadata(
            attempt_count=attempts, input_token_count=input_tokens,
            output_token_count=output_tokens, generation_duration_ms=duration,
            device=device,
        ),
        processed_at=at,
    )
