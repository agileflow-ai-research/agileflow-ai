import re
from dataclasses import dataclass

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType as A,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticResultStatus,
)

from .canonicalization import (
    ENTITY_FIELD_PATTERN,
    MALFORMED_API_PATTERN,
    api_operations,
    canonical_feature_name,
    deterministic_id,
    external_ids,
    fingerprint,
    lexical_jaccard,
    normalize_identifier,
)
from .constants import (
    LEXICAL_JACCARD_THRESHOLD,
    LEXICAL_MINIMUM_SHARED_TOKENS,
    TRACEABILITY_ENGINE_VERSION,
)
from .schemas import (
    AmbiguousTraceabilityMatch,
    TraceabilityEvidenceMethod,
    TraceabilityLink,
    TraceabilityNode,
    TraceabilityNodeKind,
    TraceabilityRelationType,
    TraceabilityStrength,
    UnresolvedReferenceType,
    UnresolvedTraceabilityReference,
)


ARTIFACT_NODE_KIND = {
    A.FUNCTIONAL_REQUIREMENTS: TraceabilityNodeKind.FUNCTIONAL_REQUIREMENT,
    A.NON_FUNCTIONAL_REQUIREMENTS: TraceabilityNodeKind.NON_FUNCTIONAL_REQUIREMENT,
    A.USER_STORIES: TraceabilityNodeKind.USER_STORY,
    A.ACCEPTANCE_CRITERIA: TraceabilityNodeKind.ACCEPTANCE_CRITERION,
    A.FEATURES: TraceabilityNodeKind.FEATURE,
    A.API_SPECIFICATION: TraceabilityNodeKind.API_CONTRACT_ITEM,
    A.DATABASE_SCHEMA: TraceabilityNodeKind.DATA_ENTITY,
    A.UI_FLOW: TraceabilityNodeKind.UI_FLOW_STEP,
    A.WIREFRAMES: TraceabilityNodeKind.UI_ELEMENT,
    A.SYSTEM_ARCHITECTURE: TraceabilityNodeKind.ARCHITECTURE_COMPONENT,
}
ID_NODE_KIND = {
    "FR": TraceabilityNodeKind.FUNCTIONAL_REQUIREMENT,
    "NFR": TraceabilityNodeKind.NON_FUNCTIONAL_REQUIREMENT,
    "US": TraceabilityNodeKind.USER_STORY,
    "AC": TraceabilityNodeKind.ACCEPTANCE_CRITERION,
    "FEATURE": TraceabilityNodeKind.FEATURE,
}


@dataclass(frozen=True)
class TraceabilityComponents:
    nodes: list[TraceabilityNode]
    links: list[TraceabilityLink]
    unresolved: list[UnresolvedTraceabilityReference]
    ambiguities: list[AmbiguousTraceabilityMatch]


def _node(*, project_id, source_id, artifact_type, kind, display, identity,
          chunk_id=None, external_id=None, fact_id=None, start=None, end=None,
          api_method=None, api_path=None, entity=None, field=None, feature=None,
          hybrid_id=None, effective_id=None, review_id=None):
    display = " ".join(display.split())[:500]
    canonical = (
        f"{api_method} {api_path}" if api_method else
        f"{normalize_identifier(entity)}.{normalize_identifier(field)}" if field else
        normalize_identifier(entity) if entity else
        canonical_feature_name(feature) if feature else
        external_id or " ".join(display.casefold().split())
    )
    payload = {
        "version": TRACEABILITY_ENGINE_VERSION, "project": project_id,
        "source": source_id, "kind": kind.value, "identity": identity,
    }
    return TraceabilityNode(
        node_id=deterministic_id("A4TRN", payload), node_kind=kind,
        agent_project_id=project_id, source_id=source_id,
        artifact_type=artifact_type, external_reference_id=external_id,
        chunk_id=chunk_id, semantic_fact_id=fact_id,
        display_value=display or canonical, canonical_value=canonical,
        provenance_fingerprint=fingerprint(payload),
        evidence_start=start, evidence_end=end, api_method=api_method,
        api_path=api_path, entity_name=normalize_identifier(entity) if entity else None,
        field_name=normalize_identifier(field) if field else None,
        feature_name=canonical_feature_name(feature) if feature else None,
        hybrid_result_id=hybrid_id, effective_result_id=effective_id,
        review_id=review_id,
    )


def _link(source, target, relation, method, strength, reason, references,
          explanation, matched=None, score=None):
    evidence = {
        "references": sorted(set(references)), "matched": sorted(matched or []),
        "score": score,
    }
    identity = {
        "version": TRACEABILITY_ENGINE_VERSION,
        "source": source.node_id, "target": target.node_id,
        "relation": relation.value, "method": method.value,
        "evidence": evidence,
    }
    return TraceabilityLink(
        traceability_link_id=deterministic_id("A4TRL", identity),
        source_node_id=source.node_id, target_node_id=target.node_id,
        relation_type=relation, evidence_method=method,
        evidence_references=evidence["references"], reason_code=reason,
        explanation=explanation, matched_tokens=evidence["matched"],
        lexical_score=score, strength=strength,
        traceability_version=TRACEABILITY_ENGINE_VERSION,
    )


def _unresolved(source, reference_type, value, reason, start=None, end=None):
    identity = {
        "version": TRACEABILITY_ENGINE_VERSION, "source": source.node_id,
        "type": reference_type.value, "value": value, "reason": reason,
        "start": start, "end": end,
    }
    return UnresolvedTraceabilityReference(
        unresolved_id=deterministic_id("A4TRU", identity),
        source_node_id=source.node_id, reference_type=reference_type,
        reference_value=value, reason_code=reason,
        evidence_start=start, evidence_end=end,
    )


def _ambiguity(source, candidates, method, value, reason):
    ids = sorted(item.node_id for item in candidates)
    identity = {
        "version": TRACEABILITY_ENGINE_VERSION, "source": source.node_id,
        "candidates": ids, "method": method.value, "value": value,
    }
    return AmbiguousTraceabilityMatch(
        ambiguity_id=deterministic_id("A4TRA", identity),
        source_node_id=source.node_id, candidate_node_ids=ids,
        evidence_method=method, reference_value=value, reason_code=reason,
    )


def build_traceability_components(*, project_id, sources, chunk_sets,
                                  effective_manifests, semantic_manifests):
    nodes, links, unresolved, ambiguities = [], [], [], []
    chunk_nodes = {}
    node_text = {}

    for source in sorted(sources, key=lambda item: item.source_id):
        if source.source_type is TestGenerationInputSourceType.IMAGE:
            display = source.label or source.original_filename or source.artifact_type.value
            image_node = _node(
                project_id=project_id, source_id=source.source_id,
                artifact_type=source.artifact_type,
                kind=TraceabilityNodeKind.GENERIC_EVIDENCE, display=display,
                identity={"image_metadata": source.source_id},
            )
            nodes.append(image_node)
            unresolved.append(_unresolved(
                image_node, UnresolvedReferenceType.IMAGE_PENDING_ANALYSIS,
                display, "IMAGE_HAS_NO_TRUSTED_TEXT_EVIDENCE",
            ))
            continue
        chunks = chunk_sets[source.source_id]
        for chunk in chunks.chunks:
            kind = ARTIFACT_NODE_KIND.get(chunk.artifact_type, TraceabilityNodeKind.GENERIC_EVIDENCE)
            base = _node(
                project_id=project_id, source_id=source.source_id,
                artifact_type=chunk.artifact_type, kind=kind,
                display=chunk.text, identity={"chunk": chunk.chunk_id},
                chunk_id=chunk.chunk_id,
            )
            nodes.append(base)
            chunk_nodes[chunk.chunk_id] = base
            node_text[base.node_id] = chunk.text
            _extract_chunk_nodes(chunk, nodes, node_text)
            for match in MALFORMED_API_PATTERN.finditer(chunk.text):
                unresolved.append(_unresolved(
                    base, UnresolvedReferenceType.API_ENDPOINT, match.group(0),
                    "MALFORMED_API_ENDPOINT", match.start(), match.end(),
                ))

    effective_by_chunk = {
        result.chunk.chunk_id: result
        for manifest in effective_manifests.values() for result in manifest.results
    }
    for source_id, manifest in sorted(semantic_manifests.items()):
        for result in manifest.results:
            if result.status not in {SemanticResultStatus.SUCCESS, SemanticResultStatus.SUCCESS_WITH_WARNINGS}:
                continue
            effective = effective_by_chunk.get(result.chunk.chunk_id)
            for fact in result.facts:
                fact_api = (
                    api_operations(f"{fact.api_method} {fact.api_endpoint}")
                    if fact.api_method and fact.api_endpoint else []
                )
                fact_node = _node(
                    project_id=project_id, source_id=source_id,
                    artifact_type=result.chunk.artifact_type,
                    kind=TraceabilityNodeKind.SEMANTIC_TESTING_FACT,
                    display=fact.evidence_quote,
                    identity={"fact": fact.fact_id, "semantic": result.semantic_result_id},
                    chunk_id=result.chunk.chunk_id, fact_id=fact.fact_id,
                    start=fact.evidence_start, end=fact.evidence_end,
                    api_method=fact_api[0][0] if fact_api else None,
                    api_path=fact_api[0][1] if fact_api else None,
                    entity=fact.target if fact.field_name else None,
                    field=fact.field_name,
                    hybrid_id=result.hybrid_result_id,
                    effective_id=result.effective_result_id,
                    review_id=effective.review_id if effective else None,
                )
                nodes.append(fact_node)
                node_text[fact_node.node_id] = fact.evidence_quote
                target = chunk_nodes[result.chunk.chunk_id]
                references = [fact.fact_id, result.semantic_result_id, result.hybrid_result_id]
                if result.effective_result_id:
                    references.append(result.effective_result_id)
                if effective and effective.review_id:
                    references.append(effective.review_id)
                links.append(_link(
                    fact_node, target, TraceabilityRelationType.SUPPORTED_BY,
                    TraceabilityEvidenceMethod.EXPLICIT_REFERENCE,
                    TraceabilityStrength.EXACT, "FACT_GROUNDED_IN_CHUNK",
                    references,
                    "Validated semantic fact is grounded in its exact trusted chunk evidence.",
                ))

    nodes = _dedupe_nodes(nodes)
    by_external = {}
    for node in nodes:
        if node.external_reference_id:
            by_external.setdefault(node.external_reference_id, []).append(node)
    chunks_with_declared_items = {
        node.chunk_id for node in nodes if node.external_reference_id
    }
    for source in nodes:
        if source.external_reference_id is None and source.chunk_id in chunks_with_declared_items:
            continue
        text = node_text.get(source.node_id, source.display_value)
        seen_refs = set()
        for value, start, end in external_ids(text):
            if value == source.external_reference_id or value in seen_refs:
                continue
            seen_refs.add(value)
            candidates = [item for item in by_external.get(value, []) if item.node_id != source.node_id]
            if len(candidates) == 1:
                target = candidates[0]
                relation = _explicit_relation(source.node_kind, target.node_kind)
                links.append(_link(
                    source, target, relation, TraceabilityEvidenceMethod.EXPLICIT_ID,
                    TraceabilityStrength.EXACT, "EXPLICIT_ID_RESOLVED",
                    [source.chunk_id or source.node_id, value],
                    "A trusted evidence item explicitly names an existing stable identifier.",
                ))
            elif len(candidates) > 1:
                ambiguities.append(_ambiguity(
                    source, candidates, TraceabilityEvidenceMethod.EXPLICIT_ID,
                    value, "EXPLICIT_ID_HAS_MULTIPLE_TARGETS",
                ))
            else:
                unresolved.append(_unresolved(
                    source, UnresolvedReferenceType.EXPLICIT_ID, value,
                    "EXPLICIT_ID_TARGET_NOT_FOUND", start, end,
                ))

    structured_links, structured_ambiguities = _structured_matches(nodes)
    links.extend(structured_links)
    ambiguities.extend(structured_ambiguities)
    strong_pairs = {frozenset((item.source_node_id, item.target_node_id)) for item in links}
    links.extend(_lexical_matches(nodes, strong_pairs))
    links = _dedupe_links(links)
    unresolved = sorted({item.unresolved_id: item for item in unresolved}.values(), key=lambda item: item.unresolved_id)
    ambiguities = sorted({item.ambiguity_id: item for item in ambiguities}.values(), key=lambda item: item.ambiguity_id)
    return TraceabilityComponents(nodes, links, unresolved, ambiguities)


def _extract_chunk_nodes(chunk, nodes, node_text):
    text = chunk.text
    for line_number, raw in enumerate(text.splitlines() or [text]):
        line = raw.strip()
        if not line:
            continue
        ids = external_ids(line)
        if ids and re.match(r"^\s*(?:FR|NFR|US|AC|FEAT(?:URE)?)[- ]", line, re.I):
            value, _, _ = ids[0]
            prefix = value.split("-", 1)[0]
            item = _node(
                project_id=chunk.agent_project_id, source_id=chunk.source_id,
                artifact_type=chunk.artifact_type, kind=ID_NODE_KIND[prefix],
                display=line, identity={"chunk": chunk.chunk_id, "external": value},
                chunk_id=chunk.chunk_id, external_id=value,
            )
            nodes.append(item)
            node_text[item.node_id] = line
        feature = re.match(r"^\s*Feature\s*[:.-]\s*(.+)$", line, re.I)
        if feature and not ids:
            item = _node(
                project_id=chunk.agent_project_id, source_id=chunk.source_id,
                artifact_type=chunk.artifact_type, kind=TraceabilityNodeKind.FEATURE,
                display=line, identity={"chunk": chunk.chunk_id, "feature": canonical_feature_name(feature.group(1))},
                chunk_id=chunk.chunk_id, feature=feature.group(1),
            )
            nodes.append(item)
            node_text[item.node_id] = line
    for method, path, start, end in api_operations(text):
        item = _node(
            project_id=chunk.agent_project_id, source_id=chunk.source_id,
            artifact_type=chunk.artifact_type, kind=TraceabilityNodeKind.API_ENDPOINT,
            display=text[start:end], identity={"chunk": chunk.chunk_id, "api": [method, path]},
            chunk_id=chunk.chunk_id, start=start, end=end,
            api_method=method, api_path=path,
        )
        nodes.append(item)
        node_text[item.node_id] = text[start:end]
    entities = set()
    for match in re.finditer(r"\b(?:Entity|Table)\s*[:#-]\s*([A-Za-z][A-Za-z0-9_]*)", text, re.I):
        entities.add(match.group(1))
    for match in re.finditer(r"\bCREATE\s+TABLE\s+([A-Za-z][A-Za-z0-9_]*)", text, re.I):
        entities.add(match.group(1))
    for entity in sorted(entities, key=str.casefold):
        item = _node(
            project_id=chunk.agent_project_id, source_id=chunk.source_id,
            artifact_type=chunk.artifact_type, kind=TraceabilityNodeKind.DATA_ENTITY,
            display=entity, identity={"chunk": chunk.chunk_id, "entity": normalize_identifier(entity)},
            chunk_id=chunk.chunk_id, entity=entity,
        )
        nodes.append(item)
        node_text[item.node_id] = entity
    for match in ENTITY_FIELD_PATTERN.finditer(text):
        entity, field = match.groups()
        item = _node(
            project_id=chunk.agent_project_id, source_id=chunk.source_id,
            artifact_type=chunk.artifact_type, kind=TraceabilityNodeKind.DATA_FIELD,
            display=match.group(0), identity={"chunk": chunk.chunk_id, "field": [normalize_identifier(entity), normalize_identifier(field)]},
            chunk_id=chunk.chunk_id, start=match.start(), end=match.end(),
            entity=entity, field=field,
        )
        nodes.append(item)
        node_text[item.node_id] = match.group(0)


def _explicit_relation(source_kind, target_kind):
    if source_kind is TraceabilityNodeKind.USER_STORY and target_kind in {
        TraceabilityNodeKind.FUNCTIONAL_REQUIREMENT,
        TraceabilityNodeKind.NON_FUNCTIONAL_REQUIREMENT,
    }:
        return TraceabilityRelationType.REFINES
    if source_kind is TraceabilityNodeKind.ACCEPTANCE_CRITERION and target_kind is TraceabilityNodeKind.USER_STORY:
        return TraceabilityRelationType.VALIDATES
    return TraceabilityRelationType.REFERENCES


def _structured_matches(nodes):
    links, ambiguities = [], []
    for attribute, method, relation, strength, reason in (
        ("api_path", TraceabilityEvidenceMethod.API_ENDPOINT, TraceabilityRelationType.RELATED_TO, TraceabilityStrength.EXACT, "SAME_API_OPERATION"),
        ("field_name", TraceabilityEvidenceMethod.ENTITY_FIELD, TraceabilityRelationType.RELATED_TO, TraceabilityStrength.EXACT, "SAME_ENTITY_FIELD"),
        ("entity_name", TraceabilityEvidenceMethod.ENTITY_FIELD, TraceabilityRelationType.RELATED_TO, TraceabilityStrength.STRONG, "SAME_ENTITY"),
        ("feature_name", TraceabilityEvidenceMethod.FEATURE_NAME, TraceabilityRelationType.RELATED_TO, TraceabilityStrength.STRONG, "SAME_FEATURE_NAME"),
    ):
        groups = {}
        for node in nodes:
            value = getattr(node, attribute)
            if not value:
                continue
            key = (node.api_method, node.api_path) if attribute == "api_path" else (
                (node.entity_name, node.field_name) if attribute == "field_name" else value
            )
            groups.setdefault(key, []).append(node)
        for key, group in groups.items():
            semantic_nodes = [
                item for item in group
                if item.node_kind is TraceabilityNodeKind.SEMANTIC_TESTING_FACT
            ]
            evidence_nodes = [
                item for item in group
                if item.node_kind is not TraceabilityNodeKind.SEMANTIC_TESTING_FACT
            ]
            ambiguous_semantic_ids = set()
            if len(evidence_nodes) > 1:
                for semantic_node in semantic_nodes:
                    ambiguities.append(_ambiguity(
                        semantic_node, evidence_nodes, method, str(key),
                        "STRUCTURED_REFERENCE_HAS_MULTIPLE_TARGETS",
                    ))
                    ambiguous_semantic_ids.add(semantic_node.node_id)
            for index, left in enumerate(sorted(group, key=lambda item: item.node_id)):
                for right in sorted(group, key=lambda item: item.node_id)[index + 1:]:
                    if (
                        left.source_id == right.source_id
                        and left.chunk_id == right.chunk_id
                        and TraceabilityNodeKind.SEMANTIC_TESTING_FACT
                        not in {left.node_kind, right.node_kind}
                    ):
                        continue
                    if left.node_id in ambiguous_semantic_ids or right.node_id in ambiguous_semantic_ids:
                        continue
                    source, target = (left, right)
                    chosen_relation = relation
                    if left.node_kind is TraceabilityNodeKind.SEMANTIC_TESTING_FACT:
                        source, target = left, right
                        chosen_relation = {
                            "api_path": TraceabilityRelationType.USES_ENDPOINT,
                            "field_name": TraceabilityRelationType.USES_FIELD,
                            "entity_name": TraceabilityRelationType.USES_ENTITY,
                        }.get(attribute, relation)
                    elif right.node_kind is TraceabilityNodeKind.SEMANTIC_TESTING_FACT:
                        source, target = right, left
                        chosen_relation = {
                            "api_path": TraceabilityRelationType.USES_ENDPOINT,
                            "field_name": TraceabilityRelationType.USES_FIELD,
                            "entity_name": TraceabilityRelationType.USES_ENTITY,
                        }.get(attribute, relation)
                    links.append(_link(
                        source, target, chosen_relation, method, strength, reason,
                        [source.node_id, target.node_id],
                        "Trusted evidence resolves to the same canonical structured reference.",
                    ))
    return links, ambiguities


def _lexical_matches(nodes, strong_pairs):
    candidates = [
        node for node in nodes
        if node.chunk_id and node.node_kind is not TraceabilityNodeKind.SEMANTIC_TESTING_FACT
        and not any((node.external_reference_id, node.api_path, node.field_name, node.feature_name))
    ]
    links = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            pair = frozenset((left.node_id, right.node_id))
            if left.source_id == right.source_id or pair in strong_pairs:
                continue
            score, shared = lexical_jaccard(left.display_value, right.display_value)
            if score < LEXICAL_JACCARD_THRESHOLD or len(shared) < LEXICAL_MINIMUM_SHARED_TOKENS:
                continue
            source, target = sorted((left, right), key=lambda item: item.node_id)
            links.append(_link(
                source, target, TraceabilityRelationType.RELATED_TO,
                TraceabilityEvidenceMethod.LEXICAL_SIMILARITY,
                TraceabilityStrength.SUPPORTING, "CONSERVATIVE_LEXICAL_OVERLAP",
                [source.chunk_id, target.chunk_id],
                "Evidence shares a conservative deterministic token set.",
                matched=shared, score=round(score, 6),
            ))
    return links


def _dedupe_nodes(nodes):
    return sorted({item.node_id: item for item in nodes}.values(), key=lambda item: item.node_id)


def _dedupe_links(links):
    return sorted({item.traceability_link_id: item for item in links}.values(), key=lambda item: item.traceability_link_id)
