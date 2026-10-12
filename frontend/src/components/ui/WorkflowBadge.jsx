import { workflowStagePresentation } from '../../utils/workflowPresentation.js'
import StatusBadge from './StatusBadge.jsx'

function WorkflowBadge({ stage, className }) {
  const presentation = workflowStagePresentation(stage)

  return (
    <StatusBadge
      label={presentation.label}
      tone={presentation.tone}
      className={className}
    />
  )
}

export default WorkflowBadge
