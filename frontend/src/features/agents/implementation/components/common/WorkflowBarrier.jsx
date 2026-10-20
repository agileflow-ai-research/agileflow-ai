import Button from '../../../../../components/ui/Button.jsx'
import HumanDecisionCallout from './HumanDecisionCallout.jsx'

function WorkflowBarrier({ gate, onNavigate }) {
  return (
    <HumanDecisionCallout
      eyebrow={gate.failed ? 'Action required after failure' : 'Blocked'}
      title={gate.failed ? 'This stage needs attention before the workflow can continue.' : 'Complete the upstream decision first.'}
      description={gate.blocking_reason}
      outcome="The workflow remains unchanged until the prerequisite is completed and validated."
    >
      {gate.blocking_node_id ? (
        <Button variant="outline" onClick={() => onNavigate?.(gate.blocking_node_id)}>
          Go to prerequisite
        </Button>
      ) : null}
    </HumanDecisionCallout>
  )
}

export default WorkflowBarrier
