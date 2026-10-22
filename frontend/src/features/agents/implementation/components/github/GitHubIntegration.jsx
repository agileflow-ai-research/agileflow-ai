import Button from '../../../../../components/ui/Button.jsx'
import Card from '../../../../../components/ui/Card.jsx'
import Input from '../../../../../components/ui/Input.jsx'
import Select from '../../../../../components/ui/Select.jsx'
import Textarea from '../../../../../components/ui/Textarea.jsx'

export default function GitHubIntegration({
  githubState,
  repositoryForm,
  repositoryState,
  setRepositoryForm,
  setRepositoryState,
  onConnect,
  onCreateRepository,
}) {
  return (
      <Card aria-labelledby="github-integration-title">
        <h3 id="github-integration-title" className="text-card-heading font-semibold text-content-primary">GitHub Integration</h3>
        {githubState.notice && <p role="status" className="mt-3 text-sm text-state-success">{githubState.notice}</p>}
        {githubState.error && <p role="alert" className="mt-3 text-sm text-state-danger">{githubState.error}</p>}
        {githubState.status === 'connected' ? (
          <div className="mt-4 space-y-5">
            <div className="flex flex-wrap items-start gap-4">
              {githubState.connection.avatar_url && (
                <img className="h-12 w-12 rounded-full" src={githubState.connection.avatar_url} alt={`@${githubState.connection.github_login} GitHub avatar`} />
              )}
              <dl className="grid gap-2 text-sm">
                <div><dt className="inline font-medium text-content-primary">Status: </dt><dd className="inline text-state-success">Connected</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account: </dt><dd className="inline text-content-secondary">@{githubState.connection.github_login}</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account type: </dt><dd className="inline text-content-secondary">Personal</dd></div>
              </dl>
            </div>

            {repositoryState.error && <p role="alert" className="text-sm text-state-danger">{repositoryState.error}</p>}
            {repositoryState.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading repository status...</p>}
            {repositoryState.status === 'ready' || repositoryState.status === 'creating' ? (
              <section aria-labelledby="repository-setup-title" className="space-y-4 border-t border-default pt-5">
                <div>
                  <h4 id="repository-setup-title" className="font-semibold text-content-primary">Repository Setup</h4>
                  <p className="mt-1 text-sm text-content-secondary">Create one new, empty repository in your connected personal GitHub account.</p>
                </div>
                <Input
                  label="Repository Name"
                  required
                  value={repositoryForm.name}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => {
                    setRepositoryForm((current) => ({ ...current, name: event.target.value }))
                    setRepositoryState((current) => ({ ...current, error: '' }))
                  }}
                />
                <Textarea
                  label="Description"
                  rows={3}
                  value={repositoryForm.description}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, description: event.target.value }))}
                />
                <Select
                  label="Visibility"
                  required
                  value={repositoryForm.visibility}
                  disabled={repositoryState.status === 'creating'}
                  options={[
                    { value: 'PRIVATE', label: 'Private' },
                    { value: 'PUBLIC', label: 'Public' },
                  ]}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, visibility: event.target.value }))}
                />
                <Button
                  loading={repositoryState.status === 'creating'}
                  loadingLabel="Creating repository"
                  onClick={onCreateRepository}
                >
                  Create Repository
                </Button>
              </section>
            ) : null}
            {repositoryState.status === 'created' && repositoryState.repository ? (
              <section aria-labelledby="created-repository-title" className="space-y-3 border-t border-default pt-5">
                <h4 id="created-repository-title" className="font-semibold text-content-primary">Repository</h4>
                <p className="text-state-success">Created</p>
                <p className="font-semibold text-content-primary">{repositoryState.repository.full_name}</p>
                <dl className="grid gap-2 text-sm">
                  <div><dt className="inline font-medium text-content-primary">Visibility: </dt><dd className="inline text-content-secondary">{repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Repository state: </dt><dd className="inline text-content-secondary">Empty</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Branch structure: </dt><dd className="inline text-content-secondary">Not created yet</dd></div>
                </dl>
                <a className="inline-flex text-sm font-semibold text-accent hover:underline" href={repositoryState.repository.html_url} target="_blank" rel="noreferrer">Open on GitHub</a>
              </section>
            ) : null}
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm text-content-secondary">Connect your GitHub account so Agent 3 can create a new repository.</p>
            <div className="mt-4">
              <Button
                loading={githubState.status === 'connecting'}
                loadingLabel="Starting GitHub connection"
                disabled={githubState.status === 'loading'}
                onClick={onConnect}
              >
                Connect GitHub
              </Button>
            </div>
          </>
        )}
      </Card>
  )
}
