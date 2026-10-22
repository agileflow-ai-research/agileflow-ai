import GitHubIntegration from '../components/github/GitHubIntegration.jsx'
import Button from '../../../../components/ui/Button.jsx'
import HumanDecisionCallout from '../components/common/HumanDecisionCallout.jsx'

export default function DeliverySetupPanel({ githubState, repositoryState, deliveryDecision, integrationProps, onContinue }) {
  const repository = repositoryState.repository
  const deliveryComplete = Boolean(repository) || deliveryDecision === 'SKIPPED'
  return (
    <div className="space-y-5">
      {deliveryComplete ? (
        <section className="rounded-control border border-state-success/40 bg-state-success/10 p-4" role="status">
          <h3 className="font-semibold text-content-primary">✓ Delivery setup complete</h3>
          <p className="mt-2 text-sm text-content-secondary">The implementation plan is ready for final approval.</p>
        </section>
      ) : <HumanDecisionCallout
        eyebrow="Delivery choice"
        title="How should the generated implementation be delivered?"
        description="Choose the configured GitHub repository or continue without repository delivery. No Git operation is performed at this stage."
        evidence={repository?.full_name ? `Configured repository: ${repository.full_name}` : 'No repository is currently configured.'}
        outcome="Your delivery choice unlocks the separate final implementation approval."
      />}
      <section aria-labelledby="delivery-destination-title">
        <h3 id="delivery-destination-title" className="font-semibold text-content-primary">Delivery destination</h3>
        <dl className="mt-3 grid gap-2 text-sm">
          <div><dt className="inline text-content-muted">GitHub Account: </dt><dd className="inline text-content-primary">{githubState.connection?.connected ? `Connected as @${githubState.connection.github_login}` : githubState.status === 'loading' ? 'Loading' : 'Not connected'}</dd></div>
          <div><dt className="inline text-content-muted">Repository: </dt><dd className="inline text-content-primary">{repository?.full_name ?? 'Not created yet'}</dd></div>
          {repository ? <div><dt className="inline text-content-muted">Visibility: </dt><dd className="inline text-content-primary">{repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</dd></div> : null}
        </dl>
      </section>
      <GitHubIntegration {...integrationProps} />
      {!deliveryComplete ? <div className="rounded-control border border-default bg-elevated p-4">
        <p className="text-sm text-content-secondary">Repository delivery is optional for implementation approval. You can configure it now or continue without it.</p>
        <Button className="mt-3" onClick={onContinue}>
          {repository ? 'Continue to Final Approval' : 'Continue Without Repository Delivery'}
        </Button>
      </div> : null}
    </div>
  )
}
