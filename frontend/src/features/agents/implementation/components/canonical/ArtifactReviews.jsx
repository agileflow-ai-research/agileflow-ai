import {
  canonicalSourceLabel,
  canonicalStatusLabel,
  detectionLabel,
} from '../../utils/presentation.js'

export function CanonicalArtifactReview({ result }) {
  const groups = result.artifacts.reduce((current, artifact) => {
    current[artifact.artifact_type] = [...(current[artifact.artifact_type] || []), artifact]
    return current
  }, {})
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Canonical Artifact Review">
      {Object.entries(groups).map(([type, artifacts]) => (
        <section key={type} className="space-y-3">
          <h4 className="font-semibold text-content-primary">{detectionLabel(type)}</h4>
          {artifacts.map((artifact) => (
            <article key={artifact.artifact_id} className="rounded-lg border border-default p-3 text-sm">
              <p className="font-medium text-content-primary">{artifact.artifact_id}</p>
              <p className={artifact.status === 'UNRESOLVED' ? 'text-state-warning' : 'text-content-secondary'}>
                Status: {canonicalStatusLabel(artifact.status)}
              </p>
              <p className="mt-2 font-medium text-content-primary">Extracted structure</p>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-content-secondary">{JSON.stringify(artifact.data, null, 2)}</pre>
              {artifact.unresolved_items.length > 0 && (
                <div className="mt-2">
                  <p className="font-medium text-content-primary">Unresolved</p>
                  {artifact.unresolved_items.map((item, index) => <p key={`${item.reason}-${index}`} className="text-state-warning">{item.reason}</p>)}
                </div>
              )}
              <div className="mt-2">
                <p className="font-medium text-content-primary">Source</p>
                {artifact.source_refs.map((source) => <p key={`${source.chunk_id}-${source.text_hash}`} className="text-content-secondary">{canonicalSourceLabel(source)}</p>)}
              </div>
            </article>
          ))}
        </section>
      ))}
    </section>
  )
}

export function SemanticArtifactReview({ result }) {
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Semantic Result Review">
      {result.results.map((item) => (
        <article key={item.artifact_id} className="rounded-lg border border-default p-3 text-sm">
          <p className="font-semibold text-content-primary">{detectionLabel(item.artifact_type)}</p>
          <p className="text-content-secondary">Status: {detectionLabel(item.status)}</p>
          {item.semantic_proposal && (
            <>
              <p className="mt-2 font-medium text-content-primary">Semantic proposal</p>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-content-secondary">{JSON.stringify(item.semantic_proposal, null, 2)}</pre>
            </>
          )}
          {item.merged_preview?.field_provenance.filter((field) => field.origin === 'SEMANTIC').map((field) => (
            <div key={field.field_path} className="mt-2 rounded border border-default p-2">
              <p>Proposed field: {field.field_path}</p>
              <p>Origin: SEMANTIC</p>
              {field.evidence.map((evidence, index) => (
                <p key={`${field.field_path}-${index}`} className="text-content-secondary">Evidence: “{evidence.quote}”</p>
              ))}
              <p className="text-state-success">{'✓ Source evidence verified'}</p>
            </div>
          ))}
          {item.validation?.rejections.map((rejection) => (
            <div key={`${rejection.field_path}-${String(rejection.proposed_value)}`} className="mt-2 rounded border border-default p-2">
              <p>Rejected proposed field: {rejection.field_path} = {JSON.stringify(rejection.proposed_value)}</p>
              <p className="text-state-danger">{'✕ Unsupported by source'}</p>
              <p>Reason: {rejection.code}</p>
            </div>
          ))}
          {item.validation?.conflicts.map((conflict) => (
            <div key={`${conflict.field_path}-${JSON.stringify(conflict.semantic_value)}`} className="mt-2 rounded border border-default p-2">
              <p className="font-medium text-state-warning">Semantic / Deterministic Conflict</p>
              <p>Field: {conflict.field_path}</p>
              <p>Deterministic: {JSON.stringify(conflict.deterministic_value)}</p>
              <p>Semantic: {JSON.stringify(conflict.semantic_value)}</p>
              {conflict.semantic_evidence.map((evidence, index) => <p key={index}>Evidence: “{evidence.quote}”</p>)}
              <p>Status: Human Review Required</p>
            </div>
          ))}
        </article>
      ))}
    </section>
  )
}

