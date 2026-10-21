import NodeShellPanel from './NodeShellPanel.jsx'

function TestingIntelligencePanel({ definition, statusLabel, workflowNodeStatus }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      note={workflowNodeStatus === 'NOT_STARTED'
        ? 'Testing Intelligence is the next workflow node. Classification and semantic analysis will be implemented next; no model inference is running.'
        : 'Testing intelligence is not implemented yet. Planned research integrations are descriptive only; this shell performs no model inference.'}
    />
  )
}

export default TestingIntelligencePanel
