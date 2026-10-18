import ArtifactGroup from '../components/common/ArtifactGroup.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'
import { reviewTaxonomy } from '../constants/workspace.js'
import { sourceName } from '../utils/sourcePresentation.js'

function aggregateArtifacts(inputs) {
  const groups = new Map()
  function include(type, source, layer, status = null, verified = false) {
    if (!type || type === 'OTHER_CONTEXT') return
    const group = groups.get(type) ?? {
      type, sources: new Set(), layers: new Set(), statuses: [], verifiedCount: 0,
    }
    group.sources.add(source)
    group.layers.add(layer)
    if (status) group.statuses.push(status)
    if (verified) group.verifiedCount += 1
    groups.set(type, group)
  }

  let machineSuggestions = 0
  let verifiedReferences = 0
  inputs.forEach((input, index) => {
    const source = sourceName(input, index)
    input.hybridDetections?.chunks?.forEach((chunk) => {
      chunk.candidates?.forEach((candidate) => {
        machineSuggestions += 1
        include(candidate.label, source, 'Machine suggested')
      })
    })
    input.humanReviews?.review?.chunks?.forEach((chunk) => {
      chunk.verified_labels?.forEach((label) => {
        verifiedReferences += 1
        include(label, source, 'Human verified', 'COMPLETE', true)
      })
    })
    input.canonicalArtifacts?.artifacts?.forEach((artifact) => {
      include(artifact.artifact_type, source, 'Deterministic specification', artifact.status)
    })
    input.semanticArtifacts?.results?.forEach((artifact) => {
      include(artifact.artifact_type, source, 'Semantic preview', artifact.status)
    })
  })

  const ordered = reviewTaxonomy
    .map((type) => groups.get(type))
    .filter(Boolean)
    .map((group) => ({
      ...group,
      status: group.statuses.includes('HUMAN_REVIEW_REQUIRED') || group.statuses.includes('UNRESOLVED')
        ? 'HUMAN_REVIEW_REQUIRED'
        : group.statuses.includes('PARTIAL') ? 'PARTIAL' : group.statuses.includes('COMPLETE') ? 'COMPLETE' : null,
    }))
  return { groups: ordered, machineSuggestions, verifiedReferences }
}

export default function SpecificationVerificationPanel({ inputs, humanReviewContent, researchContent }) {
  const { groups, machineSuggestions, verifiedReferences } = aggregateArtifacts(inputs)
  const semanticMetrics = inputs.reduce((summary, input) => ({
    grounded: summary.grounded + (input.semanticArtifacts?.metrics?.accepted_fact_count ?? 0),
    rejected: summary.rejected + (input.semanticArtifacts?.metrics?.rejected_fact_count ?? 0),
    conflicts: summary.conflicts + (input.semanticArtifacts?.metrics?.conflict_count ?? 0),
  }), { grounded: 0, rejected: 0, conflicts: 0 })

  return (
    <div className="space-y-6">
      <section aria-labelledby="verification-summary-title">
        <h3 id="verification-summary-title" className="font-semibold text-content-primary">Specification summary</h3>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div className="border-l-2 border-accent-border pl-3"><dt className="text-content-muted">Machine Suggested</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{machineSuggestions}</dd></div>
          <div className="border-l-2 border-state-success pl-3"><dt className="text-content-muted">Human Verified</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{verifiedReferences}</dd></div>
        </dl>
      </section>

      <section aria-labelledby="verified-specification-title" className="space-y-4">
        <div>
          <h3 id="verified-specification-title" className="font-semibold text-content-primary">Verified Specification</h3>
          <p className="mt-1 text-sm text-content-secondary">Available file-scoped artifacts grouped across the project while preserving their source.</p>
        </div>
        {groups.length > 0 ? groups.map((group) => <ArtifactGroup key={group.type} group={group} />) : (
          <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No machine-suggested or human-verified specification artifacts are loaded yet.</p>
        )}
      </section>

      {(semanticMetrics.grounded > 0 || semanticMetrics.rejected > 0 || semanticMetrics.conflicts > 0) ? (
        <section aria-labelledby="semantic-summary-title">
          <h3 id="semantic-summary-title" className="font-semibold text-content-primary">Suggested Structured Information</h3>
          <dl className="mt-3 grid gap-2 text-sm">
            <div><dt className="inline text-content-muted">Grounded additions: </dt><dd className="inline text-content-primary">{semanticMetrics.grounded}</dd></div>
            <div><dt className="inline text-content-muted">Rejected unsupported information: </dt><dd className="inline text-content-primary">{semanticMetrics.rejected}</dd></div>
            <div><dt className="inline text-content-muted">Conflicts requiring review: </dt><dd className="inline text-content-primary">{semanticMetrics.conflicts}</dd></div>
          </dl>
        </section>
      ) : null}

      {humanReviewContent ? (
        <section aria-labelledby="human-verification-title">
          <h3 id="human-verification-title" className="font-semibold text-content-primary">Human Verification</h3>
          <p className="mt-1 text-sm text-content-secondary">Compare machine suggestions with human-verified decisions.</p>
          {humanReviewContent}
        </section>
      ) : null}

      <ResearchDetails description="Access file-level extraction, rule baseline, DeBERTa, hybrid analysis, human review controls, deterministic canonical details, semantic/Qwen previews, metrics, and provenance.">
        {researchContent}
      </ResearchDetails>
    </div>
  )
}
