import { useState } from 'react'

import Button from '../../../components/ui/Button.jsx'
import TestGenerationInputsStep from './components/inputs/TestGenerationInputsStep.jsx'
import ModeSelectionStep from './components/mode/ModeSelectionStep.jsx'
import ModeWorkflowPreview from './components/mode/ModeWorkflowPreview.jsx'
import { AGENT4_MODES } from './constants/workspace.js'

// Mode-first workspace. Choosing a mode performs no request and creates no run.
// TEST_GENERATION opens its Inputs stage, which collects project-level sources only.
// Project name and domain come from the shared AgentProject, never from this workspace.
function TestingValidationWorkspace({ project }) {
  const [mode, setMode] = useState(null)

  return (
    <div className="space-y-6">
      <dl className="grid gap-4 sm:grid-cols-2" aria-label="Project context">
        <div>
          <dt className="text-xs text-content-muted">Project</dt>
          <dd className="font-semibold text-content-primary">{project.name}</dd>
        </div>
        <div>
          <dt className="text-xs text-content-muted">Domain</dt>
          <dd className="font-semibold text-content-primary">{project.domain}</dd>
        </div>
      </dl>

      {mode ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-content-secondary">
              Mode: <span className="font-semibold text-content-primary">{AGENT4_MODES[mode].label}</span>
            </p>
            <Button variant="ghost" size="small" onClick={() => setMode(null)}>
              Change mode
            </Button>
          </div>
          <ModeWorkflowPreview mode={mode} />
          {mode === 'TEST_GENERATION' && <TestGenerationInputsStep agentProjectId={project.agent_project_id} />}
        </div>
      ) : (
        <ModeSelectionStep onSelect={setMode} />
      )}
    </div>
  )
}

export default TestingValidationWorkspace
