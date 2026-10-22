import OutputSelector from '../../../../components/agents/OutputSelector.jsx'
import Button from '../../../../components/ui/Button.jsx'
import ImplementationInputsStep from '../components/inputs/ImplementationInputsStep.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import { outputOptions } from '../constants/workspace.js'
import { hasSource } from '../utils/sourcePresentation.js'
import { PresentationSection, ResultBanner } from '../../../../components/agents/presentation/NodePresentation.jsx'

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
  const inputTypes = new Set(inputs.filter(hasSource).map((input) => input.source_type)).size
  return (
    <div className="space-y-6">
      <PresentationSection label="Input" title="Project information" description="Confirm the project context, selected outputs, and trusted sources before analysis.">
        <ResultBanner
          title={project.name}
          description={project.description?.trim() || `Implementation planning for ${project.domain || 'the selected project domain'}.`}
          metrics={[
            { label: 'Sources', value: sourceCount },
            { label: 'Selected outputs', value: selectedOutputs.length },
            { label: 'Input types', value: inputTypes },
            { label: 'Domain', value: project.domain || 'Not specified' },
          ]}
        />
      </PresentationSection>

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
