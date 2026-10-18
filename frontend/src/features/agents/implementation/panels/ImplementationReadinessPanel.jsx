import Button from '../../../../components/ui/Button.jsx'
import ReadinessReview from '../components/readiness/ReadinessReview.jsx'

export default function ImplementationReadinessPanel({ state, workspaceBusy, errors, onCheck, onAdapt, onBack }) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold text-content-primary">Trusted-context check</h3>
        <p className="mt-1 text-sm text-content-secondary">Evaluate the selected outputs against the implementation context currently supplied to Agent 3.</p>
      </div>
      {errors.inputs ? <p role="alert" className="text-sm text-state-danger">{errors.inputs}</p> : null}
      {errors.outputs ? <p role="alert" className="text-sm text-state-danger">{errors.outputs}</p> : null}
      <Button loading={state.status === 'evaluating'} loadingLabel="Evaluating implementation readiness" disabled={workspaceBusy} onClick={onCheck}>
        Check Implementation Readiness
      </Button>
      {state.error ? <p role="alert" className="text-sm text-state-danger">{state.error}</p> : null}
      {state.result ? <ReadinessReview state={state} onAdapt={onAdapt} onBack={onBack} /> : (
        <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No readiness evaluation exists yet.</p>
      )}
    </div>
  )
}
