import { detectionLabel } from '../../utils/presentation.js'
import StatusBadge from '../../../../../components/ui/StatusBadge.jsx'

function normalStatus(status) {
  if (status === 'COMPLETE') return 'Complete'
  if (status === 'PARTIAL') return 'Partial'
  if (status === 'UNRESOLVED' || status === 'HUMAN_REVIEW_REQUIRED') return 'Needs Further Interpretation'
  return 'Available'
}

export default function ArtifactGroup({ group }) {
  return (
    <section className="min-w-0 rounded-control border border-default bg-surface p-4" aria-label={detectionLabel(group.type)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h4 className="font-medium text-content-primary">{detectionLabel(group.type)}</h4>
          <p className="mt-1 text-xs text-content-muted">Sources: {[...group.sources].join(', ')}</p>
        </div>
        <StatusBadge label={normalStatus(group.status)} tone={group.status === 'COMPLETE' ? 'success' : group.status === 'HUMAN_REVIEW_REQUIRED' || group.status === 'UNRESOLVED' ? 'warning' : 'neutral'} />
      </div>
      <p className="mt-2 text-sm text-content-secondary">
        {group.verifiedCount > 0 ? `${group.verifiedCount} human-verified reference${group.verifiedCount === 1 ? '' : 's'}` : 'Machine-suggested information; human verification is not complete.'}
      </p>
      <p className="mt-1 text-xs text-content-muted">Available layers: {[...group.layers].join(', ')}</p>
    </section>
  )
}
