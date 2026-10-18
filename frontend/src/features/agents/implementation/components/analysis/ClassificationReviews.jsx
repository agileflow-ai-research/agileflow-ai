import { chunkSource, detectionLabel } from '../../utils/presentation.js'

export function RuleDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Rule Predictions">
      <div>
        <h5 className="font-semibold text-content-primary">Rule Predictions</h5>
        <p className="mt-1 text-sm text-content-secondary">Deterministic baseline {'\u2014'} no AI model used.</p>
      </div>
      {result.detections.map((detection) => {
        const chunk = chunkById.get(detection.chunk_id)
        return (
          <article key={detection.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="mt-1 text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            <p className="mt-3 text-sm font-medium text-content-primary">Detected:</p>
            <div className="mt-2 space-y-3">
              {detection.predictions.map((prediction) => (
                <div key={prediction.label}>
                  <p className="text-sm font-semibold text-content-primary">
                    {`${detectionLabel(prediction.label)} \u2014 ${detectionLabel(prediction.strength)}`}
                  </p>
                  <p className="text-sm text-content-secondary">Rule strength: {detectionLabel(prediction.strength)}</p>
                  <p className="text-sm text-content-secondary">Heuristic score: {prediction.rule_score.toFixed(2)}</p>
                  <p className="mt-1 text-sm font-medium text-content-primary">Evidence:</p>
                  <ul className="list-disc pl-5 text-sm text-content-secondary">
                    {prediction.evidence.map((evidence) => (
                      <li key={`${evidence.rule_id}-${evidence.matched_text}`}>{evidence.matched_text}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            {chunk && <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>}
          </article>
        )
      })}
    </section>
  )
}

export function ZeroShotDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Zero-Shot Predictions">
      <div>
        <h5 className="font-semibold text-content-primary">Zero-Shot Predictions</h5>
        <p className="mt-1 text-sm text-content-secondary">
          Scores are zero-shot NLI outputs and are not calibrated domain confidence.
        </p>
      </div>
      {result.chunks.map((detection) => {
        const chunk = chunkById.get(detection.chunk_id)
        return (
          <article key={detection.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="mt-1 text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            <p className="mt-2 text-sm text-content-secondary">
              Model tokens: {detection.model_token_count} / {detection.model_max_length}
            </p>
            {detection.input_truncated && <p className="text-sm text-state-warning">Input truncated for model inference</p>}
            {!detection.classification_succeeded && <p className="text-sm text-state-danger">Classification failed for this chunk</p>}
            {detection.classification_succeeded && (
              <>
                <p className="mt-3 text-sm font-medium text-content-primary">Zero-shot model predictions:</p>
                {detection.display_predictions.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-sm text-content-secondary">
                    {detection.display_predictions.map((prediction) => (
                      <li key={prediction.label}>{detectionLabel(prediction.label)}: {prediction.score.toFixed(4)}</li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-content-secondary">No label crossed the temporary display threshold.</p>}
                <p className="mt-3 text-sm font-medium text-content-primary">All taxonomy scores:</p>
                <ul className="mt-2 space-y-1 text-sm text-content-secondary">
                  {[...detection.scores].sort((left, right) => right.score - left.score).map((prediction) => (
                    <li key={prediction.label}>
                      {detectionLabel(prediction.label)}: {prediction.score.toFixed(4)}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {chunk && <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>}
          </article>
        )
      })}
    </section>
  )
}

export function HybridDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Hybrid Candidates">
      <div>
        <h5 className="font-semibold text-content-primary">Hybrid Candidates</h5>
        <p className="mt-1 text-sm text-content-secondary">Hybrid candidates are not human-verified artifacts yet.</p>
      </div>
      {result.chunks.map((record) => {
        const chunk = chunkById.get(record.chunk_id)
        const hasDisagreement = record.candidates.some((candidate) => candidate.evidence_state === 'RULE_MODEL_DISAGREEMENT')
        return (
          <article key={record.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            {record.diagnostics.model_label_explosion && (
              <p className="mt-2 text-sm text-state-warning">Warning: Zero-shot model produced several competing high-scoring labels for this chunk.</p>
            )}
            {record.diagnostics.model_ambiguous && (
              <p className="mt-2 text-sm text-state-warning">Warning: Top zero-shot scores are ambiguous.</p>
            )}
            {hasDisagreement && <p className="mt-2 text-sm text-state-warning">Needs Review: Rule and model interpretations disagree.</p>}
            {(record.diagnostics.model_label_explosion || record.diagnostics.model_ambiguous || hasDisagreement) && (
              <ul className="mt-1 text-sm text-content-secondary">
                {record.diagnostics.top_model_scores.map((score) => (
                  <li key={score.label}>{detectionLabel(score.label)}: {score.score.toFixed(4)}</li>
                ))}
              </ul>
            )}
            <div className="mt-3 space-y-4">
              {record.candidates.map((candidate) => (
                <section key={candidate.label} aria-label={`${detectionLabel(candidate.label)} hybrid candidate`}>
                  <p className="font-semibold text-content-primary">Candidate: {detectionLabel(candidate.label)}</p>
                  <p className="text-sm text-content-secondary">Decision: {candidate.decision === 'AUTO_CANDIDATE' ? 'Likely Candidate' : detectionLabel(candidate.decision)}</p>
                  <p className="text-sm text-content-secondary">Evidence state: {detectionLabel(candidate.evidence_state)}</p>
                  <p className="mt-1 text-sm text-content-secondary">
                    Rule baseline: {candidate.rule.matched ? `${detectionLabel(candidate.rule.strength)} (score ${candidate.rule.score.toFixed(2)})` : 'No matching deterministic rule'}
                  </p>
                  {candidate.rule.evidence.map((evidence) => (
                    <p key={`${evidence.rule_id}-${evidence.matched_text}`} className="text-sm text-content-secondary">Evidence: {evidence.matched_text}</p>
                  ))}
                  <p className="text-sm text-content-secondary">Zero-shot DeBERTa: {candidate.model.score == null ? 'No score' : candidate.model.score.toFixed(4)}</p>
                  <p className="text-sm text-content-secondary">Reason: {candidate.reason_codes.join(', ')}</p>
                </section>
              ))}
            </div>
          </article>
        )
      })}
    </section>
  )
}

