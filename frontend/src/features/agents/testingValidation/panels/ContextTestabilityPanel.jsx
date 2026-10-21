import NodeShellPanel from './NodeShellPanel.jsx'

function ContextTestabilityPanel({ definition, statusLabel, workflowNodeStatus }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      note={workflowNodeStatus === 'NOT_STARTED'
        ? 'Context & Testability is the next workflow node. No N4 analysis has started.'
        : 'Context and testability processing is not implemented yet. This shell performs no traceability, readiness, or feasibility calculation.'}
    />
  )
}

export default ContextTestabilityPanel
