from app.modules.agents.testing_validation.details.schemas import (
    ClassificationDetail,
    ClassificationDetailsPage,
    ContextDetailProjection,
    EvidenceRequirement,
    OutputAnalysisDetail,
    PreparedSection,
    PreparedSectionsPage,
    ReviewDecisionDetail,
    ReviewDecisionsPage,
    TestingFactDetail,
    TestingFactsPage,
    TraceabilityConnection,
)
from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.workflow.service import (
    Agent4WorkflowStageError,
    WrongAgent4WorkflowProjectError,
)


class Agent4DetailUnavailableError(ValueError):
    pass


class Agent4DetailSourceNotFoundError(ValueError):
    pass


def _page(items, offset, limit):
    return items[offset:offset + limit], len(items), offset + limit < len(items)


class Agent4DetailService:
    """Projects validated persisted artifacts without running any Agent 4 stage."""

    def __init__(
        self, standalone_service, workflow_storage, source_storage, chunk_storage,
        rule_storage, zero_storage, hybrid_storage, effective_storage,
        semantic_storage, traceability_storage, testability_storage,
        feasibility_storage, decision_storage,
    ):
        self._standalone = standalone_service
        self._workflow_storage = workflow_storage
        self._sources = source_storage
        self._chunks = chunk_storage
        self._rules = rule_storage
        self._zero = zero_storage
        self._hybrid = hybrid_storage
        self._effective = effective_storage
        self._semantic = semantic_storage
        self._traceability = traceability_storage
        self._testability = testability_storage
        self._feasibility = feasibility_storage
        self._decision = decision_storage

    def _context(self, project_id, user):
        project = self._standalone.require_active_project(user.user_id, project_id)
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise WrongAgent4WorkflowProjectError(
                "Agent project must have agent_type TESTING_VALIDATION"
            )
        if project.agent_stage is not AgentStage.TEST_GENERATION:
            raise Agent4WorkflowStageError(
                "Agent project must have agent_stage TEST_GENERATION"
            )
        workflow = self._workflow_storage.load(
            agent_project_id=project_id, owner_user_id=user.user_id,
        )
        if not workflow or not workflow.n1_confirmation:
            raise Agent4DetailUnavailableError("Confirm Input & Output Setup before viewing persisted details.")
        sources = self._sources.list_for_project(
            agent_project_id=project_id, owner_user_id=user.user_id,
        )
        confirmed = set(workflow.n1_confirmation.source_ids)
        source_by_id = {item.source_id: item for item in sources if item.source_id in confirmed}
        return workflow, source_by_id

    @staticmethod
    def _select_sources(source_by_id, source_id):
        if source_id and source_id not in source_by_id:
            raise Agent4DetailSourceNotFoundError("The confirmed source was not found.")
        return [source_by_id[source_id]] if source_id else list(source_by_id.values())

    def prepared_sections(self, project_id, user, *, source_id, offset, limit):
        _, source_by_id = self._context(project_id, user)
        items = []
        for source in self._select_sources(source_by_id, source_id):
            manifest = self._chunks.load(
                agent_project_id=project_id, owner_user_id=user.user_id,
                source_id=source.source_id,
            )
            if not manifest:
                continue
            for chunk in manifest.chunks:
                items.append(PreparedSection(
                    chunk_id=chunk.chunk_id, source_id=source.source_id,
                    source_label=source.label or source.original_filename or source.artifact_type.value.replace("_", " ").title(),
                    artifact_type=source.artifact_type.value, sequence=chunk.sequence,
                    section_count=len(manifest.chunks), text=chunk.text,
                    heading_path=chunk.heading_path, structure_type=chunk.structure_type,
                    token_count=chunk.token_count,
                ))
        page, total, more = _page(items, offset, limit)
        return PreparedSectionsPage(offset=offset, limit=limit, total=total, has_more=more, items=page)

    def classifications(self, project_id, user, *, source_id, offset, limit):
        _, source_by_id = self._context(project_id, user)
        items = []
        for source in self._select_sources(source_by_id, source_id):
            chunks = self._chunks.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
            hybrid = self._hybrid.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
            if not chunks or not hybrid:
                continue
            rules = self._rules.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
            effective = self._effective.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
            chunk_by_id = {item.chunk_id: item for item in chunks.chunks}
            rule_by_chunk = {item.chunk.chunk_id: item for item in (rules.results if rules else [])}
            effective_by_chunk = {item.chunk.chunk_id: item for item in (effective.results if effective else [])}
            for result in hybrid.results:
                chunk = chunk_by_id[result.chunk.chunk_id]
                rule_result = rule_by_chunk.get(chunk.chunk_id)
                effective_result = effective_by_chunk.get(chunk.chunk_id)
                effective_by_label = {item.label: item for item in (effective_result.decisions if effective_result else [])}
                evidence_by_label = {
                    item.label: item for item in (rule_result.rule_evidence if rule_result else [])
                }
                for decision in result.decisions:
                    effective_decision = effective_by_label.get(decision.label)
                    evidence = evidence_by_label.get(decision.label)
                    items.append(ClassificationDetail(
                        source_id=source.source_id,
                        source_label=source.label or source.original_filename or source.artifact_type.value.replace("_", " ").title(),
                        chunk_id=chunk.chunk_id, sequence=chunk.sequence,
                        label=decision.label.value,
                        evidence_quote=evidence.quote if evidence and evidence.quote else chunk.text,
                        rule_detected=decision.rule_detected,
                        model_score=decision.model_score,
                        hybrid_relationship=decision.evidence_state.value,
                        hybrid_decision=decision.status.value,
                        effective_decision=effective_decision.status.value if effective_decision else None,
                        effective_origin=effective_decision.origin.value if effective_decision else None,
                        review_id=effective_decision.review_id if effective_decision else None,
                        reason_codes=decision.reason_codes,
                        explanation=decision.explanation,
                    ))
        page, total, more = _page(items, offset, limit)
        return ClassificationDetailsPage(offset=offset, limit=limit, total=total, has_more=more, items=page)

    def review_decisions(self, project_id, user, *, offset, limit):
        _, source_by_id = self._context(project_id, user)
        record = self._workflow_storage.load(agent_project_id=project_id, owner_user_id=user.user_id)
        items = []
        for event in record.n3_review_history if record else []:
            for resolution in event.resolutions:
                source = source_by_id.get(resolution.source_id)
                if not source:
                    continue
                chunks = self._chunks.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
                chunk = next((item for item in (chunks.chunks if chunks else []) if item.chunk_id == resolution.chunk_id), None)
                effective = self._effective.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
                effective_result = next((item for item in (effective.results if effective else []) if item.chunk.chunk_id == resolution.chunk_id), None)
                effective_decision = next((item for item in (effective_result.decisions if effective_result else []) if item.label.value == resolution.label), None)
                items.append(ReviewDecisionDetail(
                    review_id=event.review_id, source_id=source.source_id,
                    source_label=source.label or source.original_filename or source.artifact_type.value.replace("_", " ").title(),
                    chunk_id=resolution.chunk_id,
                    evidence_quote=chunk.text if chunk else None,
                    label=resolution.label, human_decision=resolution.decision.value,
                    note=resolution.note,
                    effective_decision=effective_decision.status.value if effective_decision else None,
                    reviewed_at=event.reviewed_at,
                ))
        page, total, more = _page(items, offset, limit)
        return ReviewDecisionsPage(offset=offset, limit=limit, total=total, has_more=more, items=page)

    def testing_facts(self, project_id, user, *, source_id, offset, limit):
        _, source_by_id = self._context(project_id, user)
        items = []
        excluded = {"fact_id", "fact_type", "related_labels", "evidence_quote", "evidence_start", "evidence_end"}
        for source in self._select_sources(source_by_id, source_id):
            manifest = self._semantic.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source.source_id)
            if not manifest:
                continue
            for result in manifest.results:
                for fact in result.facts:
                    values = {
                        key: value for key, value in fact.model_dump(mode="json").items()
                        if key not in excluded and value not in (None, "", [])
                    }
                    items.append(TestingFactDetail(
                        fact_id=fact.fact_id, source_id=source.source_id,
                        source_label=source.label or source.original_filename or source.artifact_type.value.replace("_", " ").title(),
                        chunk_id=result.chunk.chunk_id, sequence=result.chunk.sequence,
                        fact_type=fact.fact_type.value,
                        related_labels=[item.value for item in fact.related_labels],
                        evidence_quote=fact.evidence_quote, structured_values=values,
                    ))
        page, total, more = _page(items, offset, limit)
        return TestingFactsPage(offset=offset, limit=limit, total=total, has_more=more, items=page)

    def context_details(self, project_id, user, *, offset, limit):
        self._context(project_id, user)
        owner = user.user_id
        traceability = self._traceability.load(agent_project_id=project_id, owner_user_id=owner)
        testability = self._testability.load(agent_project_id=project_id, owner_user_id=owner)
        feasibility = self._feasibility.load(agent_project_id=project_id, owner_user_id=owner)
        decision = self._decision.load(agent_project_id=project_id, owner_user_id=owner)
        if not all((traceability, testability, feasibility, decision)):
            raise Agent4DetailUnavailableError("Detailed Context & Testability evidence is not available yet.")
        nodes = {item.node_id: item for item in traceability.nodes}
        all_connections = [TraceabilityConnection(
            link_id=item.traceability_link_id,
            source_value=nodes[item.source_node_id].display_value,
            source_kind=nodes[item.source_node_id].node_kind.value,
            relation=item.relation_type.value,
            target_value=nodes[item.target_node_id].display_value,
            target_kind=nodes[item.target_node_id].node_kind.value,
            explanation=item.explanation, strength=item.strength.value,
        ) for item in traceability.links]
        connections, total, more = _page(all_connections, offset, limit)
        tb_by_output = {item.output_code: item for item in testability.output_assessments}
        fb_by_output = {item.output_code: item for item in feasibility.output_assessments}
        finding_by_id = {item.consolidated_finding_id: item for item in decision.consolidated_findings}
        outputs = []
        for profile in decision.output_profiles:
            tb = tb_by_output[profile.output_code]
            fb = fb_by_output[profile.output_code]
            requirement = lambda item: EvidenceRequirement(
                requirement_id=item.requirement_id, description=item.description,
                satisfied=item.satisfied, observed_count=item.observed_count,
            )
            outputs.append(OutputAnalysisDetail(
                output_code=profile.output_code.value,
                testability_status=profile.testability_status.value,
                mandatory_requirements=[requirement(item) for item in tb.mandatory_requirements],
                supporting_requirements=[requirement(item) for item in tb.supporting_requirements],
                feasibility_status=profile.feasibility_status.value,
                recommended_representation=profile.recommended_representation.value if profile.recommended_representation else None,
                generation_profile=fb.generation_profile.model_dump(mode="json") if fb.generation_profile else None,
                decision=profile.decision.value, planning_allowed=profile.planning_allowed,
                blockers=[finding_by_id[item].display_message for item in profile.blocking_finding_ids],
                warnings=[finding_by_id[item].display_message for item in profile.warning_finding_ids],
                evidence_node_count=len(profile.evidence_node_ids),
                evidence_link_count=len(profile.evidence_link_ids),
                semantic_fact_count=len(profile.semantic_fact_ids),
            ))
        return ContextDetailProjection(
            overall_testability=testability.overall_status.value,
            overall_feasibility=feasibility.overall_feasibility.value,
            overall_decision=decision.overall_decision.value,
            traceability_total=total, traceability_offset=offset,
            traceability_limit=limit, traceability_has_more=more,
            connections=connections, outputs=outputs,
        )
