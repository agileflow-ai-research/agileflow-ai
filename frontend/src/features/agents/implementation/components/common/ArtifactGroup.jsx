import { detectionLabel } from '../../utils/presentation.js'

function normalStatus(status) {
  if (status === 'COMPLETE') return 'Complete'
  if (status === 'PARTIAL') return 'Partial'
  if (status === 'UNRESOLVED' || status === 'HUMAN_REVIEW_REQUIRED') return 'Needs Further Interpretation'
  return 'Available'
}

export default function ArtifactGroup({ group }) {
  return (
    <section className="border-b border-default pb-4 last:border-b-0" aria-label={detectionLabel(group.type)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h4 className="font-medium text-content-primary">{detectionLabel(group.type)}</h4>
          <p className="mt-1 text-xs text-content-muted">Sources: {[...group.sources].join(', ')}</p>
        </div>
        <span className="text-xs font-semibold text-content-secondary">{normalStatus(group.status)}</span>
      </div>
      <p className="mt-2 text-sm text-content-secondary">
        {group.verifiedCount > 0 ? `${group.verifiedCount} human-verified reference${group.verifiedCount === 1 ? '' : 's'}` : 'Machine-suggested information; human verification is not complete.'}
      </p>
      <p className="mt-1 text-xs text-content-muted">Available layers: {[...group.layers].join(', ')}</p>
    </section>
  )
}
