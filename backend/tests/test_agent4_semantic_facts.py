import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.agents.testing_validation.intelligence.hybrid.storage import Agent4HybridStorage
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.semantic import constants
from app.modules.agents.testing_validation.intelligence.semantic.eligibility import (
    semantic_classification_context,
)
from app.modules.agents.testing_validation.intelligence.semantic.extractor import (
    SemanticExtractionFailedError,
    extract_semantic_result,
    generation_configuration_fingerprint,
    parse_one_object,
)
from app.modules.agents.testing_validation.intelligence.semantic.prompt import (
    build_semantic_prompt,
)
from app.modules.agents.testing_validation.intelligence.semantic.runtime import (
    Agent4QwenRuntime,
    SemanticRuntimeOutput,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticEligibility,
)
from app.modules.agents.testing_validation.intelligence.semantic.service import (
    Agent4SemanticFactService,
)
from app.modules.agents.testing_validation.intelligence.semantic.storage import (
    Agent4SemanticStorage,
    Agent4SemanticStorageError,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TestingIntelligenceLabel as Label,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import Agent4ZeroShotStorage
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.service import StandaloneService
from test_agent4_hybrid_classification import hybrid_service, paired
from test_agent4_n2_orchestration import add_text, confirm, create_project, load, n2_context
from test_agent4_rule_classification import service_for as rule_service_for
from test_agent4_testing_intelligence_contracts import chunk
from test_agent4_zero_shot_classification import FakeRuntime
from test_agent4_zero_shot_classification import service_for as zero_service_for
from test_standalone_foundation import user


NOW = datetime(2026, 5, 1, tzinfo=UTC)


class FakeSemanticRuntime:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return SemanticRuntimeOutput(value, 120, 40, 5, "cpu")


def fact_output(**overrides):
    fact = {
        "fact_type": "AUTHORIZATION_RULE",
        "related_labels": ["AUTHORIZATION"],
        "evidence_quote": "Only administrators may delete another user's booking.",
        "role": "administrators",
        "action": "delete",
        "target": "booking",
    }
    fact.update(overrides)
    return json.dumps({"facts": [fact]})


def eligible_pair(scores=None):
    rule, model = paired(scores=scores or {Label.AUTHORIZATION: .6})
    from app.modules.agents.testing_validation.intelligence.hybrid.engine import decide_hybrid_for_chunk
    return rule, model, decide_hybrid_for_chunk(rule, model, processed_at=NOW)


def extract(outputs, *, scores=None):
    _, _, hybrid = eligible_pair(scores)
    item = chunk()
    runtime = FakeSemanticRuntime(outputs)
    result = extract_semantic_result(
        chunk=item, chunk_reference=hybrid.chunk, hybrid_result=hybrid,
        accepted_labels=hybrid.accepted_labels, runtime=runtime,
        processed_at=NOW,
    )
    return runtime, result


def test_pinned_qwen_and_generation_configuration_are_exact_and_deterministic():
    assert constants.SEMANTIC_MODEL_ID == "Qwen/Qwen3-1.7B"
    assert constants.SEMANTIC_MODEL_REVISION == "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    assert constants.DO_SAMPLE is False
    assert constants.MAX_SEMANTIC_INPUT_TOKENS == 4096
    assert constants.MAX_SEMANTIC_NEW_TOKENS == 2048
    assert constants.MAX_SEMANTIC_ATTEMPTS == 2
    assert (constants.SEMANTIC_SCHEMA_VERSION, constants.SEMANTIC_STAGE_VERSION,
            constants.SEMANTIC_PROMPT_VERSION) == ("1", "S1", "SP1")
    assert generation_configuration_fingerprint() == generation_configuration_fingerprint()


def test_runtime_is_lazy_at_construction():
    class Loader:
        calls = []
        @classmethod
        def load(cls, **kwargs):
            cls.calls.append(kwargs)
            raise AssertionError("must remain lazy")
    Agent4QwenRuntime(loader=Loader)
    assert Loader.calls == []


def test_runtime_generation_is_deterministic_token_bounded_and_not_truncated():
    import torch

    class Tokenizer:
        pad_token_id = None
        eos_token_id = 9
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["enable_thinking"] is False
            return "rendered"
        def __call__(self, text, **kwargs):
            assert kwargs["truncation"] is False
            return {"input_ids": torch.tensor([[1, 2]]),
                    "attention_mask": torch.tensor([[1, 1]])}
        def decode(self, tokens, **kwargs):
            return '{"facts":[]}'

    class Model:
        def generate(self, **kwargs):
            assert kwargs["do_sample"] is False
            assert kwargs["max_new_tokens"] == 2048
            assert kwargs["stopping_criteria"]
            return torch.tensor([[1, 2, 3]])

    class Loader:
        @staticmethod
        def load(**kwargs):
            return SimpleNamespace(model=Model(), tokenizer=Tokenizer(), device="cpu")

    output = Agent4QwenRuntime(loader=Loader).generate("prompt")
    assert output.text == '{"facts":[]}'
    assert (output.input_token_count, output.output_token_count) == (2, 1)


def test_runtime_rejects_oversized_prompt_without_generation():
    import torch
    from app.modules.agents.testing_validation.intelligence.semantic.runtime import (
        SemanticInputTooLargeError,
    )

    class Tokenizer:
        pad_token_id = eos_token_id = 9
        def apply_chat_template(self, *args, **kwargs):
            return "rendered"
        def __call__(self, *args, **kwargs):
            return {"input_ids": torch.zeros((1, 4097), dtype=torch.int64)}

    class Loader:
        @staticmethod
        def load(**kwargs):
            return SimpleNamespace(model=object(), tokenizer=Tokenizer(), device="cpu")

    with pytest.raises(SemanticInputTooLargeError, match="SEMANTIC_INPUT_TOO_LARGE"):
        Agent4QwenRuntime(loader=Loader).generate("prompt")


@pytest.mark.parametrize(
    ("accepted", "review", "expected"),
    [
        ([Label.AUTHORIZATION], [], SemanticEligibility.ELIGIBLE),
        ([Label.AUTHORIZATION, Label.FUNCTIONAL_BEHAVIOR], [], SemanticEligibility.ELIGIBLE),
        ([Label.AUTHORIZATION], [Label.SECURITY_CONTROL], SemanticEligibility.WAITING_FOR_CLASSIFICATION_REVIEW),
        ([], [], SemanticEligibility.NOT_APPLICABLE),
        ([Label.NON_TESTABLE_CONTEXT], [], SemanticEligibility.NOT_APPLICABLE),
    ],
)
def test_semantic_eligibility_is_pure_and_review_safe(accepted, review, expected):
    _, _, base = eligible_pair()
    hybrid = base.model_copy(update={
        "accepted_labels": accepted,
        "review_required_labels": review,
    })
    assert semantic_classification_context(hybrid).eligibility is expected


def test_prompt_is_deterministic_grounded_json_only_and_excludes_scores_and_rejections():
    text = chunk().text
    first = build_semantic_prompt(text, [Label.AUTHORIZATION])
    second = build_semantic_prompt(text, [Label.AUTHORIZATION])
    assert first == second
    assert text in first and "AUTHORIZATION" in first
    assert "JSON object" in first and "exact verbatim evidence_quote" in first
    assert "Do not generate tests" in first
    assert "model_score" not in first and "REJECTED" not in first


@pytest.mark.parametrize("raw", ["```json\n{}\n```", "prose {}", "{} trailing", "{}{}", "[]"])
def test_parser_requires_one_plain_json_object(raw):
    with pytest.raises(ValueError):
        parse_one_object(raw)


def test_valid_grounded_fact_and_exact_offsets_are_server_owned():
    runtime, result = extract([fact_output()])
    assert result.status == "SUCCESS" and len(result.facts) == 1
    fact = result.facts[0]
    assert fact.evidence_quote == chunk().text
    assert (fact.evidence_start, fact.evidence_end) == (0, len(chunk().text))
    assert fact.fact_id.startswith("A4FACT-")
    assert len(runtime.prompts) == 1


def test_invalid_json_and_schema_retry_once_then_succeed():
    runtime, result = extract(["not-json", fact_output()])
    assert result.status == "SUCCESS"
    assert result.generation.attempt_count == 2
    assert "CORRECTION_REQUIRED=SEMANTIC_INVALID_JSON" in runtime.prompts[1]


def test_two_invalid_attempts_raise_typed_failure():
    runtime = FakeSemanticRuntime(["bad", "still bad"])
    _, _, hybrid = eligible_pair()
    with pytest.raises(SemanticExtractionFailedError):
        extract_semantic_result(
            chunk=chunk(), chunk_reference=hybrid.chunk, hybrid_result=hybrid,
            accepted_labels=hybrid.accepted_labels, runtime=runtime,
            processed_at=NOW,
        )
    assert len(runtime.prompts) == 2


def test_partial_candidates_keep_grounded_fact_with_warning_and_deduplicate():
    good = json.loads(fact_output())["facts"][0]
    bad = {**good, "minimum": 8}
    runtime, result = extract([json.dumps({"facts": [good, bad, good]})])
    assert result.status == "SUCCESS_WITH_WARNINGS"
    assert len(result.facts) == 1
    assert result.rejected_candidate_count == 1
    assert len(result.warnings) == 1
    assert len(runtime.prompts) == 1


@pytest.mark.parametrize("change", [
    {"minimum": 8},
    {"api_endpoint": "/api/bookings"},
    {"http_status": 201},
    {"evidence_quote": "administrators delete booking"},
    {"related_labels": ["API_CONTRACT"]},
    {"related_labels": ["NON_TESTABLE_CONTEXT"]},
])
def test_unsupported_values_quotes_and_labels_are_rejected_then_fail(change):
    with pytest.raises(SemanticExtractionFailedError):
        extract([fact_output(**change), fact_output(**change)])


def test_ambiguous_repeated_quote_requires_offsets():
    item = chunk().model_copy(update={
        "text": "booking booking",
        "text_sha256": __import__("hashlib").sha256(b"booking booking").hexdigest(),
    })
    _, _, hybrid = eligible_pair()
    candidate = {
        "facts": [{
            "fact_type": "BEHAVIOR", "related_labels": ["AUTHORIZATION"],
            "evidence_quote": "booking", "target": "booking",
        }]
    }
    runtime = FakeSemanticRuntime([json.dumps(candidate), json.dumps(candidate)])
    with pytest.raises(SemanticExtractionFailedError):
        extract_semantic_result(
            chunk=item, chunk_reference=hybrid.chunk, hybrid_result=hybrid,
            accepted_labels=hybrid.accepted_labels, runtime=runtime,
            processed_at=NOW,
        )


def test_empty_facts_is_distinct_valid_empty_result():
    _, result = extract(['{"facts":[]}'])
    assert result.status == "EMPTY" and result.facts == []


def test_fact_and_result_ids_ignore_time_and_device():
    _, first = extract([fact_output()])
    _, _, hybrid = eligible_pair()
    second_runtime = FakeSemanticRuntime([fact_output()])
    second = extract_semantic_result(
        chunk=chunk(), chunk_reference=hybrid.chunk, hybrid_result=hybrid,
        accepted_labels=hybrid.accepted_labels, runtime=second_runtime,
        processed_at=NOW + timedelta(days=1),
    )
    assert first.semantic_result_id == second.semantic_result_id
    assert [f.fact_id for f in first.facts] == [f.fact_id for f in second.facts]


def semantic_service(context, runtime, *, clock=lambda: NOW):
    _, _, _, root, projects, runs, _, _, _ = context
    return Agent4SemanticFactService(
        StandaloneService(projects, runs), Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root), Agent4RuleStorage(root),
        Agent4ZeroShotStorage(root), Agent4HybridStorage(root),
        Agent4SemanticStorage(root), runtime, clock=clock,
    )


def prepared(context, *, text="The system shall create a booking.", model_score=.6):
    client, _, executor, _, _, _, _, _, _ = context
    project_id = create_project(client)
    source = add_text(client, project_id, text)
    confirm(client, project_id)
    executor.drain()
    rule_service_for(context).build(project_id, source["source_id"], user())
    zero_service_for(context, FakeRuntime(scores=[model_score] * 15)).build(
        project_id, source["source_id"], user()
    )
    hybrid_service(context).build(project_id, source["source_id"], user())
    return client, project_id, source


def behavior_output():
    return json.dumps({"facts": [{
        "fact_type": "BEHAVIOR",
        "related_labels": ["FUNCTIONAL_BEHAVIOR"],
        "evidence_quote": "The system shall create a booking.",
        "action": "create", "target": "booking",
    }]})


def test_service_persists_separately_reuses_cache_and_preserves_all_inputs(n2_context):
    client, project_id, source = prepared(n2_context)
    root = n2_context[3]
    before = {path: path.read_bytes() for path in (root / project_id).rglob("*") if path.is_file()}
    runtime = FakeSemanticRuntime([behavior_output()])
    service = semantic_service(n2_context, runtime)
    first = service.build(project_id, source["source_id"], user())
    path = root / project_id / "intelligence" / f"{source['source_id']}.semantic-facts.json"
    raw = path.read_bytes()
    cached = service.build(project_id, source["source_id"], user())
    assert cached == first and path.read_bytes() == raw and len(runtime.prompts) == 1
    assert all(path.read_bytes() == value for path, value in before.items())
    workflow = load(client, project_id)
    assert workflow["current_node_id"] == "TESTING_INTELLIGENCE"
    assert workflow["nodes"][2]["status"] == "NOT_STARTED"
    assert workflow["nodes"][3]["status"] == "LOCKED"
    assert n2_context[5].documents == {}


def test_waiting_review_and_not_applicable_do_not_invoke_runtime(n2_context):
    _, waiting_project, waiting_source = prepared(n2_context, model_score=.1)
    waiting_runtime = FakeSemanticRuntime([])
    waiting = semantic_service(n2_context, waiting_runtime).build(
        waiting_project, waiting_source["source_id"], user()
    )
    assert waiting.results[0].status == "WAITING_FOR_CLASSIFICATION_REVIEW"
    assert waiting_runtime.prompts == []

    _, empty_project, empty_source = prepared(
        n2_context, text="Project background information.", model_score=.1
    )
    empty_runtime = FakeSemanticRuntime([])
    empty = semantic_service(n2_context, empty_runtime).build(
        empty_project, empty_source["source_id"], user()
    )
    assert empty.results[0].status == "NOT_APPLICABLE"
    assert empty_runtime.prompts == []


def test_force_rebuild_only_reruns_semantic_and_preserves_ids(n2_context):
    _, project_id, source = prepared(n2_context)
    runtime = FakeSemanticRuntime([behavior_output(), behavior_output()])
    service = semantic_service(n2_context, runtime)
    first = service.build(project_id, source["source_id"], user())
    service._clock = lambda: NOW + timedelta(seconds=1)
    second = service.build(project_id, source["source_id"], user(), force=True)
    assert len(runtime.prompts) == 2
    assert first.results[0].semantic_result_id == second.results[0].semantic_result_id
    assert first.results[0].facts[0].fact_id == second.results[0].facts[0].fact_id


def test_missing_hybrid_rejected_and_failed_extraction_writes_no_manifest(n2_context):
    _, project_id, source = prepared(n2_context)
    root = n2_context[3]
    hybrid_path = root / project_id / "intelligence" / f"{source['source_id']}.hybrid.json"
    hybrid_path.unlink()
    with pytest.raises(ValueError, match="hybrid classification evidence"):
        semantic_service(n2_context, FakeSemanticRuntime([])).build(
            project_id, source["source_id"], user()
        )


def test_atomic_failure_cleans_partial(n2_context, monkeypatch):
    _, project_id, source = prepared(n2_context)
    original = Path.replace
    monkeypatch.setattr(
        Path, "replace",
        lambda self, target: (_ for _ in ()).throw(OSError("boom"))
        if self.name.endswith(".semantic-facts.json.part") else original(self, target),
    )
    with pytest.raises(Agent4SemanticStorageError):
        semantic_service(n2_context, FakeSemanticRuntime([behavior_output()])).build(
            project_id, source["source_id"], user()
        )
    assert not list((n2_context[3] / project_id).rglob("*.semantic-facts.json.part"))
