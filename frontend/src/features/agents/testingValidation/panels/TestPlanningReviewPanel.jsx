import { NextStep, ResultBanner } from './NodePresentation.jsx'

function TestPlanningReviewPanel({ definition }) {
  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    <ResultBanner tone="neutral" title="Reserved — not implemented in PP1" description="This node marks the planned test-case planning and mandatory human-review phase. It has no backend processing, generated plan, or approval action in the current workflow." />
    <NextStep>For PP1, the implemented workflow ends with the real Context &amp; Testability readiness decision.</NextStep>
  </section>
}

export default TestPlanningReviewPanel
