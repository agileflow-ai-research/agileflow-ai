import NodeShellPanel from './NodeShellPanel.jsx'

function TestPlanningReviewPanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Locked · Waiting for Context & Testability"
      note="Planning and review are not implemented yet. No Test Case Plan or review decision is created by this shell."
    >
      <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-4">
        <h4 className="font-semibold text-content-primary">Mandatory Human Approval Gate</h4>
        <p className="mt-1 text-sm text-content-secondary">Detailed test generation will remain blocked until a future reviewed Test Case Plan is approved.</p>
      </div>
    </NodeShellPanel>
  )
}

export default TestPlanningReviewPanel
