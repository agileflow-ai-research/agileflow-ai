import GitHubIntegration from '../components/github/GitHubIntegration.jsx'

export default function DeliverySetupPanel({ githubState, repositoryState, integrationProps }) {
  const repository = repositoryState.repository
  return (
    <div className="space-y-5">
      <section aria-labelledby="delivery-destination-title">
        <h3 id="delivery-destination-title" className="font-semibold text-content-primary">Delivery destination</h3>
        <dl className="mt-3 grid gap-2 text-sm">
          <div><dt className="inline text-content-muted">GitHub Account: </dt><dd className="inline text-content-primary">{githubState.connection?.connected ? `Connected as @${githubState.connection.github_login}` : githubState.status === 'loading' ? 'Loading' : 'Not connected'}</dd></div>
          <div><dt className="inline text-content-muted">Repository: </dt><dd className="inline text-content-primary">{repository?.full_name ?? 'Not created yet'}</dd></div>
          {repository ? <div><dt className="inline text-content-muted">Visibility: </dt><dd className="inline text-content-primary">{repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</dd></div> : null}
        </dl>
      </section>
      <GitHubIntegration {...integrationProps} />
    </div>
  )
}
