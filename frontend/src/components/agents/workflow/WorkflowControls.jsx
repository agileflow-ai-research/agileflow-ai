import Button from '../../ui/Button.jsx'

function WorkflowControls({ onAutoArrange, onResetLayout }) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Workflow layout controls">
      <Button variant="outline" size="small" onClick={onAutoArrange}>Auto Arrange</Button>
      <Button variant="ghost" size="small" onClick={onResetLayout}>Reset Layout</Button>
    </div>
  )
}

export default WorkflowControls
