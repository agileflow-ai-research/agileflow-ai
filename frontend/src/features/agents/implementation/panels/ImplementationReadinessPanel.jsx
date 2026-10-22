import Button from '../../../../components/ui/Button.jsx'
import ReadinessReview from '../components/readiness/ReadinessReview.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'

export default function ImplementationReadinessPanel({ state, workspaceBusy, errors, onCheck, onAdapt, onBack, onContinueWithWarnings, specificationStatus }) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold text-content-primary">Trusted project readiness</h3>
        <p className="mt-1 text-sm text-content-secondary">Agent 3 evaluates selected outputs only against the current final trusted project specification.</p>
      </div>
      {errors.outputs ? <p role="alert" className="text-sm text-state-danger">{errors.outputs}</p> : null}
      {specificationStatus && specificationStatus !== 'READY' ? <p role="alert" className="rounded-control border border-default p-4 text-sm text-state-danger">Project specification is {specificationStatus.replaceAll('_', ' ').toLowerCase()}. Readiness cannot be trusted until Specification Verification is ready.</p> : null}
      {state.status === 'evaluating' ? <p role="status" className="text-sm text-content-secondary">Checking implementation readiness...</p> : null}
      {state.error ? <p role="alert" className="text-sm text-state-danger">{state.error}</p> : null}
      {state.result ? <ReadinessReview
        state={state}
        onAdapt={onAdapt}
        onBack={onBack}
        onContinueWithWarnings={onContinueWithWarnings}
      /> : (
        <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No readiness evaluation exists yet.</p>
      )}
      <ResearchDetails description="Manual evaluation is retained for research and recovery use.">
        <Button loading={state.status === 'evaluating'} loadingLabel="Evaluating implementation readiness" disabled={workspaceBusy || Boolean(specificationStatus && specificationStatus !== 'READY')} onClick={onCheck}>
          Re-evaluate Readiness
        </Button>
      </ResearchDetails>
    </div>
  )
}
