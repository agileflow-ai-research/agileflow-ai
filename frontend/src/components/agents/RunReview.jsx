import Card from '../ui/Card.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { getAgentRunModePresentation } from '../../utils/agentPresentation.js'

function RunReview({ project, sections = [], selectedOutputs = [], runMode = 'DEFAULT' }) {
  const mode = getAgentRunModePresentation(runMode)

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-content-primary">{project?.name ?? 'Project'}</h3>
            {project?.domain && <p className="mt-1 text-sm text-content-secondary">{project.domain}</p>}
          </div>
          <StatusBadge label={mode.label} tone="accent" />
        </div>
      </Card>

      {sections.map((section) => (
        <Card key={section.id ?? section.title}>
          <h3 className="font-semibold text-content-primary">{section.title}</h3>
          <div className="mt-3 text-body-copy text-content-secondary">{section.content}</div>
        </Card>
      ))}

      <Card>
        <h3 className="font-semibold text-content-primary">Selected outputs</h3>
        {selectedOutputs.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2" aria-label="Selected outputs">
            {selectedOutputs.map((output) => (
              <li key={output}>
                <StatusBadge label={output} tone="neutral" />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-body-copy text-content-secondary">No outputs selected.</p>
        )}
      </Card>
    </div>
  )
}

export default RunReview
