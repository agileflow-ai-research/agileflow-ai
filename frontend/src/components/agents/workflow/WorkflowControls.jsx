import Button from '../../ui/Button.jsx'

function WorkflowControls({ onAutoArrange, onResetLayout }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-control border border-default/80 bg-canvas/50 p-1" aria-label="Workflow layout controls">
      <Button variant="ghost" size="small" className="px-2.5" onClick={onAutoArrange}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4" aria-hidden="true"><rect x="3" y="4" width="7" height="6" rx="1.5" /><rect x="14" y="14" width="7" height="6" rx="1.5" /><path d="M10 7h4a3 3 0 0 1 3 3v4M7 10v4a3 3 0 0 0 3 3h4" /></svg>
        Auto Arrange
      </Button>
      <Button variant="ghost" size="small" className="px-2.5" onClick={onResetLayout}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6" /><path d="M4 4v4.6h4.6" /></svg>
        Reset Layout
      </Button>
    </div>
  )
}

export default WorkflowControls
