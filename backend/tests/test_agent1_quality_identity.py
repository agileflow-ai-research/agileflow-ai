from app.modules.agents.requirements.quality.identity import quality_input_identity


def test_quality_input_identity_is_stable_and_order_sensitive():
    values = dict(
        agent_project_id="AGP-020", n3_execution_id="N3-AAAAAAAAAAAAAAAA-001",
        n3_attempt=1, discovery_input_identity="a" * 64,
        chunk_set_digest="b" * 64, candidate_artifact_digest="c" * 64,
        classification_artifact_digest="d" * 64,
        structured_artifact_digest="e" * 64, structured_set_identity="f" * 64,
        classifier_configuration_fingerprint="1" * 64,
        ordered_requirement_ids=("FR-AAAAAAAAAAAAAAAA", "NFR-BBBBBBBBBBBBBBBB"),
    )
    first = quality_input_identity(**values)
    assert first == quality_input_identity(**values)
    values["ordered_requirement_ids"] = tuple(reversed(values["ordered_requirement_ids"]))
    assert first != quality_input_identity(**values)
