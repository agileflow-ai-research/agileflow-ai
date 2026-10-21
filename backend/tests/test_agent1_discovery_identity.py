from app.modules.agents.requirements.discovery.identity import discovery_input_identity


def test_discovery_input_identity_is_deterministic_and_digest_sensitive():
    values = dict(agent_project_id="AGP-020", n2_execution_id="N2-AAAAAAAAAAAAAAAA-001", n2_attempt=1)
    first = discovery_input_identity(**values, chunk_set_digest="b" * 64)
    assert first == discovery_input_identity(**values, chunk_set_digest="b" * 64)
    assert first != discovery_input_identity(**values, chunk_set_digest="c" * 64)
    assert first == "dc80e8f78cbfe68ed63c549bbbb476b9406337f0c11ccb537427c8cb0b667e52"
