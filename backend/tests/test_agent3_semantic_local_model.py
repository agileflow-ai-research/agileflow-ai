import json
from types import SimpleNamespace

import pytest

from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model import constants
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.adapter import (
    LocalSemanticExtractorAdapter, SemanticModelOutputInvalidError,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.json_parser import (
    SemanticModelJsonError, parse_single_json_object,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.model_loader import (
    LoadedSemanticModel, SemanticModelLoader,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.prompt_builder import (
    build_prompt,
)
from test_agent3_semantic_extraction_contract import CHUNK_ID, api_proposal, request


class StubLoader:
    calls = []

    @classmethod
    def load(cls, **kwargs):
        cls.calls.append(kwargs)
        return LoadedSemanticModel(
            model=object(), tokenizer=object(), device="cpu",
            model_id=kwargs["model_id"], revision=kwargs["revision"],
            load_ms=25,
        )


class GeneratedAdapter(LocalSemanticExtractorAdapter):
    def __init__(self, outputs):
        super().__init__(
            model_id=constants.SEMANTIC_MODEL_ID,
            revision=constants.SEMANTIC_MODEL_REVISION,
            local_files_only=True, device="cpu", loader=StubLoader,
        )
        self.outputs = list(outputs)
        self.prompts = []

    def _generate(self, loaded, prompt, artifact_type):
        self.prompts.append(prompt)
        return self.outputs.pop(0), 120, 40, 15


def valid_output(text="POST /api/bookings"):
    return json.dumps(api_proposal(
        text, method="POST", path="/api/bookings",
    ))


def test_pinned_model_metadata_and_adapter_is_lazy():
    assert constants.SEMANTIC_MODEL_ID == "Qwen/Qwen3-1.7B"
    assert constants.SEMANTIC_MODEL_REVISION == "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    StubLoader.calls = []
    adapter = GeneratedAdapter([valid_output()])
    assert StubLoader.calls == []
    proposal = adapter.extract(request("POST /api/bookings"))
    assert proposal.artifact_type.value == "API_SPECIFICATION"
    assert StubLoader.calls[0]["local_files_only"] is True
    assert adapter.last_generation_metadata.model_id == constants.SEMANTIC_MODEL_ID
    assert adapter.last_generation_metadata.revision == constants.SEMANTIC_MODEL_REVISION
    assert adapter.last_generation_metadata.device == "cpu"


def test_loader_caches_and_forwards_revision_local_only_and_safetensors(monkeypatch):
    import torch
    import transformers

    calls = {"tokenizer": [], "model": []}

    class FakeModel:
        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained",
                        lambda *args, **kwargs: calls["tokenizer"].append((args, kwargs)) or object())
    monkeypatch.setattr(transformers.AutoModelForCausalLM, "from_pretrained",
                        lambda *args, **kwargs: calls["model"].append((args, kwargs)) or FakeModel())
    SemanticModelLoader.reset_for_tests()
    first = SemanticModelLoader.load(
        model_id=constants.SEMANTIC_MODEL_ID,
        revision=constants.SEMANTIC_MODEL_REVISION,
        local_files_only=True, device="auto",
    )
    second = SemanticModelLoader.load(
        model_id=constants.SEMANTIC_MODEL_ID,
        revision=constants.SEMANTIC_MODEL_REVISION,
        local_files_only=True, device="auto",
    )
    assert first is second
    assert first.device == "cpu"
    assert len(calls["model"]) == 1
    assert calls["model"][0][1]["use_safetensors"] is True
    assert calls["model"][0][1]["revision"] == constants.SEMANTIC_MODEL_REVISION
    assert calls["model"][0][1]["local_files_only"] is True


@pytest.mark.parametrize("output", [
    "<think>hidden reasoning</think>\n" + valid_output(),
    "reasoning first\n" + valid_output(),
    valid_output() + "\nexplanation",
    valid_output() + valid_output(),
    "[1, 2, 3]",
])
def test_json_parser_rejects_prose_reasoning_and_multiple_objects(output):
    with pytest.raises(SemanticModelJsonError):
        parse_single_json_object(output)


def test_json_parser_accepts_plain_and_one_bounded_json_fence():
    expected = {"artifact_type": "API_SPECIFICATION", "endpoints": []}
    raw = json.dumps(expected)
    assert parse_single_json_object(raw) == expected
    assert parse_single_json_object(f"```json\n{raw}\n```") == expected


def test_invalid_json_and_schema_retry_once_then_succeed():
    StubLoader.calls = []
    adapter = GeneratedAdapter(["not json", valid_output()])
    proposal = adapter.extract(request("POST /api/bookings"))
    assert proposal.artifact_type.value == "API_SPECIFICATION"
    assert adapter.last_generation_metadata.attempt_count == 2
    assert "previous attempt was invalid" in adapter.prompts[1].lower()
    assert len(StubLoader.calls) == 1

    schema_invalid = GeneratedAdapter([
        '{"artifact_type":"API_SPECIFICATION","endpoints":"wrong"}',
        valid_output(),
    ])
    assert schema_invalid.extract(request("POST /api/bookings"))
    assert schema_invalid.last_generation_metadata.attempt_count == 2


def test_max_attempts_are_enforced():
    adapter = GeneratedAdapter(["bad", "still bad", valid_output()])
    with pytest.raises(SemanticModelOutputInvalidError, match="MODEL_OUTPUT_INVALID"):
        adapter.extract(request("POST /api/bookings"))
    assert len(adapter.prompts) == constants.MAX_SEMANTIC_GENERATION_ATTEMPTS
    assert len(adapter.outputs) == 1


def test_prompt_is_artifact_specific_grounded_and_has_no_reasoning_request():
    req = request("Create a booking using name and email.")
    prompt = build_prompt(req)
    assert "Do not invent HTTP methods" in prompt
    assert "evidence.quote copied verbatim" in prompt
    assert "SOURCE_TEXT_BEGIN\nCreate a booking using name and email." in prompt
    assert '"artifact_type":"API_SPECIFICATION"' in prompt
    assert "Do not provide reasoning" in prompt
    assert "DETERMINISTIC_ARTIFACT_STATUS=PARTIAL" in prompt
    assert "DETERMINISTIC_ARTIFACT_DATA=" in prompt
    assert '"source_refs"' not in prompt


def test_generation_is_deterministic_and_token_bounded():
    import torch

    class FakeTokenizer:
        pad_token_id = None
        eos_token_id = 99

        def __init__(self):
            self.max_length = None

        def apply_chat_template(self, *args, **kwargs):
            assert kwargs["enable_thinking"] is False
            assert kwargs["continue_final_message"] is True
            assert "add_generation_prompt" not in kwargs
            assert args[0][-1] == {
                "role": "assistant",
                "content": '{"artifact_type":"FUNCTIONAL_REQUIREMENTS","requirements":',
            }
            return "rendered"

        def __call__(self, text, **kwargs):
            self.max_length = kwargs["max_length"]
            return {"input_ids": torch.tensor([[1, 2]]),
                    "attention_mask": torch.tensor([[1, 1]])}

        def decode(self, tokens, **kwargs):
            return '[]}'

    class FakeModel:
        def generate(self, **kwargs):
            assert kwargs["do_sample"] is False
            assert kwargs["max_new_tokens"] == constants.MAX_SEMANTIC_NEW_TOKENS
            assert kwargs["pad_token_id"] == 99
            return torch.tensor([[1, 2, 3]])

    tokenizer = FakeTokenizer()
    loaded = SimpleNamespace(
        tokenizer=tokenizer, model=FakeModel(), device="cpu",
    )
    output, input_count, output_count, elapsed = LocalSemanticExtractorAdapter._generate(
        loaded, "prompt", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS
    )
    assert (output, input_count, output_count) == (
        '{"artifact_type":"FUNCTIONAL_REQUIREMENTS","requirements":[]}',
        2, 1,
    )
    assert elapsed >= 0
    assert tokenizer.max_length == constants.MAX_SEMANTIC_INPUT_TOKENS
