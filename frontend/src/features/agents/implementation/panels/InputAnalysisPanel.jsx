import ResearchDetails from '../components/common/ResearchDetails.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import { hasSource, sourceAnalysisState } from '../utils/sourcePresentation.js'

export default function InputAnalysisPanel({ inputs, researchContent }) {
  const sources = inputs.filter(hasSource)
  const prepared = sources.filter((input) => sourceAnalysisState(input).label === 'Prepared').length
  const needsAttention = sources.filter((input) => sourceAnalysisState(input).label === 'Needs Attention').length
  return (
    <div className="space-y-6">
      <section aria-labelledby="analysis-overview-title">
        <h3 id="analysis-overview-title" className="font-semibold text-content-primary">Source analysis overview</h3>
        <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
          {[['Sources', sources.length], ['Prepared', prepared], ['Needs Attention', needsAttention]].map(([label, value]) => (
            <div key={label} className="border-l-2 border-accent-border pl-3"><dt className="text-content-muted">{label}</dt><dd className="mt-1 text-xl font-semibold text-content-primary">{value}</dd></div>
          ))}
        </dl>
      </section>
      <SourceSummary inputs={inputs} mode="analysis" />
      <p className="text-sm text-content-secondary">Statuses reflect only file-level results currently loaded in this workspace.</p>
      <ResearchDetails>{researchContent}</ResearchDetails>
    </div>
  )
}
