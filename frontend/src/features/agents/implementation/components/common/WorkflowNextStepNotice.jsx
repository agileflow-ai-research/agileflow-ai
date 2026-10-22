import Button from '../../../../../components/ui/Button.jsx'
import { NextStep } from '../../../../../components/agents/presentation/NodePresentation.jsx'

export default function WorkflowNextStepNotice({ title = 'Next step', description, actionLabel, targetNodeId, onNavigate }) {
  if (!description || !targetNodeId || !onNavigate) return null
  return (
    <aside className="mb-5" aria-label="Workflow next step">
      <NextStep title={title}>
        <p>{description}</p>
        <Button className="mt-3" variant="outline" size="small" onClick={() => onNavigate(targetNodeId)}>
          {actionLabel}
        </Button>
      </NextStep>
    </aside>
  )
}
