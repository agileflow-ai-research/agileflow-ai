import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  getRequiredPlanningFields,
  getValidationIssues,
  outputGroups,
  specificationSources,
} from '../constants/agent2Config.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function HumanReviewPanel({
  project,
  input = {},
  uploadProvenance = {},
  selectedOutputs = [],
  humanReviewApproved = false,
  onSetHumanReviewApproved,
  onNavigate,
}) {
  const validationIssues = getValidationIssues(input, selectedOutputs)
  const isBlocked = validationIssues.length > 0
  const requiredPlanning = getRequiredPlanningFields(selectedOutputs)

  const activeSpecs = specificationSources
    .map((source) => {
      const text = input[source.stateKey]?.trim() || ''
      const provenance = uploadProvenance[source.id] || null
      return {
        ...source,
        text,
        provenance,
        hasContent: Boolean(text),
      }
    })
    .filter((s) => s.hasContent)

  const specSourceCount = activeSpecs.length

  const selectedGroups = outputGroups
    .map((group) => ({
      ...group,
      selected: group.outputs.filter((output) => selectedOutputs.includes(output.value)),
    }))
    .filter((group) => group.selected.length > 0)

  const optionalSummaryItems = [
    { label: 'Preferred stack', value: input.preferred_technology_stack },
    { label: 'Database', value: input.database_preference },
    { label: 'Deployment', value: input.deployment_preference },
    { label: 'Architecture notes', value: input.architecture_notes },
    { label: 'Expected project duration', value: input.expected_project_duration },
    { label: 'Technical constraints', value: input.technical_constraints },
    { label: 'UI/UX constraints', value: input.ui_ux_constraints },
    { label: 'Developer roles', value: input.developer_roles },
    { label: 'Developer skills', value: input.developer_skills },
    { label: 'Team composition', value: input.team_composition },
  ].filter((item) => Boolean(item.value?.trim()))

  function handleProceed() {
    if (!isBlocked && humanReviewApproved && onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)
    }
  }

  return (
    <div className="space-y-6" data-testid="agent2-panel-HUMAN_REVIEW">
      {/* 4 Summary Metrics Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4" aria-label="Summary metrics">
        <Card className="border-default bg-[#150c2a] p-4">
          <span className="text-xs font-medium text-content-muted">Specification sources</span>
          <p className="mt-2 text-2xl font-bold text-content-primary">{specSourceCount}</p>
        </Card>
        <Card className="border-default bg-[#150c2a] p-4">
          <span className="text-xs font-medium text-content-muted">Selected outputs</span>
          <p className="mt-2 text-2xl font-bold text-content-primary">{selectedOutputs.length}</p>
        </Card>
        <Card className="border-default bg-[#150c2a] p-4">
          <span className="text-xs font-medium text-content-muted">Developers</span>
          <p className="mt-2 text-2xl font-bold text-content-primary">
            {Number(input.development_team_count) > 0 ? input.development_team_count : 'Not provided'}
          </p>
        </Card>
        <Card className="border-default bg-[#150c2a] p-4">
          <span className="text-xs font-medium text-content-muted">Sprint duration</span>
          <p className="mt-2 text-2xl font-bold text-content-primary">
            {Number(input.sprint_duration) > 0 ? `${input.sprint_duration} days` : 'Not provided'}
          </p>
        </Card>
      </div>

      {/* 1. Specifications summary card */}
      <Card className="border-default bg-[#150c2a] p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 border-b border-border-default/40 pb-3">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Specification summary ({specSourceCount})
          </h3>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)}
            className="text-xs text-[#a78bfa] hover:text-white hover:bg-brand/20 underline"
          >
            Edit Node 1
          </Button>
        </div>

        {activeSpecs.length > 0 ? (
          <div className="space-y-3">
            {activeSpecs.map((spec) => (
              <div key={spec.id} className="rounded-control border border-default bg-[#0b0517] p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-content-primary">{spec.label}</span>
                  <span className="text-[11px] text-content-muted">{spec.text.length.toLocaleString()} chars</span>
                </div>
                {spec.provenance && (
                  <div className="text-[11px] text-[#34d399] flex items-center gap-1.5">
                    <span>📄 Uploaded: {spec.provenance.original_filename}</span>
                    <span>({(spec.provenance.size_bytes / 1024).toFixed(1)} KB)</span>
                  </div>
                )}
                <p className="text-xs text-content-secondary line-clamp-2 font-mono">
                  {spec.text.slice(0, 150)}{spec.text.length > 150 ? '...' : ''}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-state-danger">
            No specification sources provided. Please provide at least one source in Node 1.
          </div>
        )}
      </Card>

      {/* 2. Selected outputs summary card */}
      <Card className="border-default bg-[#150c2a] p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 border-b border-border-default/40 pb-3">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Selected outputs ({selectedOutputs.length})
          </h3>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)}
            className="text-xs text-[#a78bfa] hover:text-white hover:bg-brand/20 underline"
          >
            Edit Node 2
          </Button>
        </div>

        {selectedGroups.length > 0 ? (
          <div className="space-y-3" aria-label="Selected outputs summary">
            {selectedGroups.map((group) => (
              <div key={group.id} className="space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                  {group.title} ({group.selected.length})
                </span>
                <div className="flex flex-wrap gap-2">
                  {group.selected.map((output) => (
                    <span
                      key={output.value}
                      className="inline-flex items-center gap-1.5 rounded-control border border-[#3c2463] bg-[#211438] px-2.5 py-1 text-xs text-content-primary"
                    >
                      <span>{output.label}</span>
                      <span className="font-mono text-[10px] text-[#a78bfa]">{output.value}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-state-danger">No outputs selected. Please select at least one output in Node 2.</p>
        )}
      </Card>

      {/* 3. Relevant Technical & Planning inputs summary card */}
      <Card className="border-default bg-[#150c2a] p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 border-b border-border-default/40 pb-3">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Technical & planning summary
          </h3>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)}
            className="text-xs text-[#a78bfa] hover:text-white hover:bg-brand/20 underline"
          >
            Edit Node 3
          </Button>
        </div>

        <div className="text-sm space-y-3">
          <p className="font-medium text-content-primary">
            {project?.name || 'BookEase'}
            {project?.domain ? ` · ${project.domain}` : ''}
          </p>

          {/* Planning parameters with requirement rationale */}
          <div className="rounded-control border border-default bg-[#0b0517] p-3.5 space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Planning parameters
            </span>
            <ul className="space-y-1.5 text-xs text-content-secondary">
              <li className="flex items-start gap-1.5">
                <span className="text-content-muted">•</span>
                <span>
                  <strong className="font-medium text-content-primary">Development team count:</strong>{' '}
                  {Number(input.development_team_count) > 0 ? input.development_team_count : 'Not provided'}
                  {requiredPlanning.development_team_count ? (
                    <span className="ml-1.5 text-[#fbbf24]">
                      ({requiredPlanning.development_team_count.reason})
                    </span>
                  ) : (
                    <span className="ml-1.5 text-content-muted">(Optional)</span>
                  )}
                </span>
              </li>
              <li className="flex items-start gap-1.5">
                <span className="text-content-muted">•</span>
                <span>
                  <strong className="font-medium text-content-primary">Sprint duration:</strong>{' '}
                  {Number(input.sprint_duration) > 0 ? `${input.sprint_duration} days` : 'Not provided'}
                  {requiredPlanning.sprint_duration ? (
                    <span className="ml-1.5 text-[#fbbf24]">
                      ({requiredPlanning.sprint_duration.reason})
                    </span>
                  ) : (
                    <span className="ml-1.5 text-content-muted">(Optional)</span>
                  )}
                </span>
              </li>
            </ul>
          </div>

          {/* Supplied technical preferences */}
          <ul className="space-y-1.5 text-content-secondary" aria-label="Supplied input preferences">
            {optionalSummaryItems.map((item) => (
              <li key={item.label} className="flex items-start gap-1.5 text-xs">
                <span className="text-content-muted">•</span>
                <span>
                  <strong className="font-medium text-content-primary">{item.label}:</strong>{' '}
                  {item.value.trim()}
                </span>
              </li>
            ))}
            {optionalSummaryItems.length === 0 && (
              <li className="text-xs text-content-muted">No additional technical preferences provided.</li>
            )}
          </ul>
        </div>
      </Card>

      {/* 4. Validation / Warnings block */}
      {isBlocked ? (
        <div
          role="alert"
          aria-label="Validation issues"
          className="rounded-panel border border-state-danger/50 bg-state-danger/10 p-5 space-y-3"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-state-danger font-bold text-base" aria-hidden="true">
                ⚠️
              </span>
              <h3 className="font-semibold text-state-danger">
                Validation Issues ({validationIssues.length}) · Human Review Blocked
              </h3>
            </div>
            <StatusBadge label="Review Blocked" tone="danger" />
          </div>
          <p className="text-sm text-content-secondary">
            Resolve the following issues in the upstream workflow nodes before human review can be approved:
          </p>
          <ul className="space-y-2 pt-1 text-sm">
            {validationIssues.map((issue) => (
              <li
                key={issue.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-state-danger/30 bg-[#120618] px-3.5 py-2 text-state-danger"
              >
                <span>• {issue.message}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onNavigate?.(issue.targetNodeId)}
                  className="text-xs text-[#a78bfa] hover:text-white hover:bg-brand/20 underline"
                >
                  Edit in {issue.targetNodeId === 'PROJECT_SPECIFICATIONS' ? 'Node 1' : issue.targetNodeId === 'OUTPUT_SELECTION' ? 'Node 2' : 'Node 3'}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div
          role="note"
          aria-label="Validation status"
          className="rounded-panel border border-[#065f46] bg-[#064e3b]/20 p-4 text-sm text-[#34d399] flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <span className="font-bold">✓</span>
            <span>All validation requirements satisfied. Specifications, planning parameters, and output deliverables are consistent.</span>
          </div>
          <StatusBadge label="Ready for Review" tone="success" />
        </div>
      )}

      {/* Standalone Human Review Checkpoint Card */}
      <Card className="border border-[#7c3aed]/50 bg-[#241344]/80 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-content-primary">
            Human review required before starting this standalone run
          </h3>
          <StatusBadge
            label={isBlocked ? 'Blocked' : humanReviewApproved ? 'Approved' : 'Pending Review'}
            tone={isBlocked ? 'danger' : humanReviewApproved ? 'success' : 'warning'}
          />
        </div>
        <p className="text-sm text-content-secondary">
          You can go back and correct inputs or output selection. This standalone flow does not invoke integrated H2 approval.
        </p>

        <label className="flex items-center gap-3 pt-2 cursor-pointer">
          <input
            type="checkbox"
            id="human-review-approval"
            checked={humanReviewApproved}
            disabled={isBlocked}
            onChange={(e) => onSetHumanReviewApproved?.(e.target.checked)}
            className="h-4 w-4 rounded accent-brand disabled:cursor-not-allowed"
          />
          <span className="text-sm font-medium text-content-primary">
            I have reviewed and confirmed the specifications, planning inputs, and output deliverables.
          </span>
        </label>
      </Card>

      {/* Footer navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={() => onNavigate?.(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)}
          className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
        >
          Back — Technical & Planning
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={isBlocked || !humanReviewApproved}
          onClick={handleProceed}
          title={
            isBlocked
              ? 'Resolve validation issues before proceeding'
              : !humanReviewApproved
                ? 'Check the review confirmation box above to proceed'
                : 'Proceed to execution'
          }
        >
          Proceed to Generate Design & Planning
        </Button>
      </div>
    </div>
  )
}
