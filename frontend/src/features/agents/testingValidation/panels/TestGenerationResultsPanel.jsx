import { NextStep, ResultBanner } from './NodePresentation.jsx'

function TestGenerationResultsPanel({ definition }) {
  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    <ResultBanner tone="neutral" title="Reserved — future development" description="Detailed test generation, executable code, execution, and result reporting are not implemented. This node displays no generated or simulated output." />
    <NextStep>No action is available in this reserved node.</NextStep>
  </section>
}

export default TestGenerationResultsPanel
