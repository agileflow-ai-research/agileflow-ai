import OutputSelector from '../../../../components/agents/OutputSelector.jsx'
import Button from '../../../../components/ui/Button.jsx'
import ImplementationInputsStep from '../components/inputs/ImplementationInputsStep.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import { outputOptions } from '../constants/workspace.js'
import { hasSource } from '../utils/sourcePresentation.js'

export default function ProjectSourcesPanel({
  project,
  inputs,
  selectedOutputs,
  onOutputsChange,
  outputError,
  inputStepProps,
  canAnalyze,
  analyzing,
  onAnalyze,
}) {
  const sourceCount = inputs.filter(hasSource).length
  return (
    <div className="space-y-6">
      <section aria-labelledby="project-information-title">
        <h3 id="project-information-title" className="font-semibold text-content-primary">Project information</h3>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-content-muted">Project</dt><dd className="font-medium text-content-primary">{project.name}</dd></div>
          <div><dt className="text-content-muted">Domain</dt><dd className="font-medium text-content-primary">{project.domain}</dd></div>
        </dl>
        {project.description?.trim() ? <p className="mt-3 text-sm text-content-secondary">{project.description}</p> : null}
      </section>

      <section aria-label="Selected Outputs">
        <OutputSelector label="Selected Outputs" options={outputOptions} selectedValues={selectedOutputs} onChange={onOutputsChange} />
        {outputError ? <p role="alert" className="mt-3 text-sm text-state-danger">{outputError}</p> : null}
      </section>

      <section aria-labelledby="source-summary-title" className="space-y-3">
        <div>
          <h3 id="source-summary-title" className="font-semibold text-content-primary">Sources — {sourceCount}</h3>
          <p className="mt-1 text-sm text-content-secondary">Text and uploaded material currently defining this implementation project.</p>
        </div>
        <SourceSummary inputs={inputs} />
      </section>

      <ImplementationInputsStep {...inputStepProps} inputs={inputs} showResearchDetails={false} />

      <div className="flex justify-end border-t border-default pt-5">
        <Button
          size="large"
          loading={analyzing}
          loadingLabel="Starting input analysis"
          disabled={!canAnalyze || analyzing}
          onClick={onAnalyze}
        >
          Next — Analyze Inputs
        </Button>
      </div>
    </div>
  )
}
