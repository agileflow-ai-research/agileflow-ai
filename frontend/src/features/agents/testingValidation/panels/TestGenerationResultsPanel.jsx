import NodeShellPanel from './NodeShellPanel.jsx'

function TestGenerationResultsPanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Locked · Waiting for approved Test Case Plan"
      note="Test generation and results are not implemented yet. This shell generates no tests and performs no execution."
    >
      <div className="rounded-control border border-default bg-elevated p-4">
        <h4 className="font-semibold text-content-primary">Stage 1 result contract</h4>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          <div><dt className="text-xs uppercase tracking-wide text-content-muted">Representation</dt><dd className="mt-1 text-sm text-content-primary">SPECIFICATION or EXECUTABLE_CODE</dd></div>
          <div><dt className="text-xs uppercase tracking-wide text-content-muted">execution_status</dt><dd className="mt-1 text-sm font-semibold text-content-primary">NOT_EXECUTED</dd></div>
        </dl>
      </div>
    </NodeShellPanel>
  )
}

export default TestGenerationResultsPanel
