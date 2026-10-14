import Spinner from '../ui/Spinner.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { getAgentRunStatusPresentation } from '../../utils/agentPresentation.js'

function ProcessingState({ status, title, description, children }) {
  const presentation = getAgentRunStatusPresentation(status)

  return (
    <section
      className="rounded-card border border-default bg-surface p-card text-center"
      aria-live="polite"
      aria-busy={status === 'QUEUED' || status === 'RUNNING'}
    >
      <Spinner className="mx-auto" label={`${presentation.label}: ${title}`} />
      <div className="mt-4 flex justify-center">
        <StatusBadge label={presentation.label} tone={presentation.tone} />
      </div>
      <h2 className="mt-4 text-card-heading font-semibold text-content-primary">{title}</h2>
      {description && <p className="mt-2 text-body-copy text-content-secondary">{description}</p>}
      {children && <div className="mt-4 text-sm text-content-muted">{children}</div>}
    </section>
  )
}

export default ProcessingState
