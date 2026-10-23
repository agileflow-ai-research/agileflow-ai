import { useEffect, useState } from 'react'
import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import Select from '../../../../components/ui/Select.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import Spinner from '../../../../components/ui/Spinner.jsx'
import {
  cleanJiraCallbackParams,
  disconnectJira,
  getJiraBoards,
  getJiraContext,
  getJiraProjects,
  getJiraSites,
  getJiraStatus,
  normalizeJiraError,
  selectJiraBoard,
  selectJiraProject,
  selectJiraSite,
  startJiraConnection,
} from '../../../../services/jiraService.js'

function JiraIntegrationSection({ project }) {
  const [loadingContext, setLoadingContext] = useState(true)
  const [context, setContext] = useState(null)
  const [statusInfo, setStatusInfo] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)
  const [successNotice, setSuccessNotice] = useState(null)

  // Sub-selection loading states
  const [loadingSites, setLoadingSites] = useState(false)
  const [sites, setSites] = useState([])
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [savingSite, setSavingSite] = useState(false)

  const [loadingProjects, setLoadingProjects] = useState(false)
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [savingProject, setSavingProject] = useState(false)

  const [loadingBoards, setLoadingBoards] = useState(false)
  const [boards, setBoards] = useState([])
  const [selectedBoardId, setSelectedBoardId] = useState('')
  const [savingBoard, setSavingBoard] = useState(false)

  // Editing overrides for changing selection
  const [isChangingSite, setIsChangingSite] = useState(false)
  const [isChangingProject, setIsChangingProject] = useState(false)
  const [isChangingBoard, setIsChangingBoard] = useState(false)

  // Connecting / Disconnecting states
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [showDisconnectModal, setShowDisconnectModal] = useState(false)

  // Initial load & OAuth callback check
  useEffect(() => {
    let isMounted = true

    async function initialize() {
      // Clean temporary OAuth callback query params if present
      const callbackResult = cleanJiraCallbackParams()
      if (callbackResult.error) {
        setErrorMessage(
          `Jira authorization was not completed (${callbackResult.error}). Please try connecting again.`,
        )
      } else if (callbackResult.connected) {
        setSuccessNotice('Jira Cloud authorized successfully!')
      }

      try {
        setLoadingContext(true)
        const [ctx, status] = await Promise.all([
          getJiraContext(),
          getJiraStatus(),
        ])
        if (!isMounted) return

        setContext(ctx)
        setStatusInfo(status)

        if (status?.reauthorization_required) {
          setErrorMessage('Your Jira connection has expired. Reconnect Jira to continue.')
        }
      } catch (err) {
        if (!isMounted) return
        setErrorMessage(normalizeJiraError(err))
      } finally {
        if (isMounted) setLoadingContext(false)
      }
    }

    initialize()
    return () => {
      isMounted = false
    }
  }, [])

  // When connected and no site selected (or changing site), fetch sites
  useEffect(() => {
    if (!context?.connected) return
    if (!context.site || isChangingSite) {
      let isMounted = true

      async function fetchSites() {
        setLoadingSites(true)
        try {
          const items = await getJiraSites()
          if (isMounted) {
            setSites(items)
            setSelectedSiteId(context.site?.cloud_id || '')
          }
        } catch (err) {
          if (isMounted) setErrorMessage(normalizeJiraError(err))
        } finally {
          if (isMounted) setLoadingSites(false)
        }
      }

      fetchSites()
      return () => {
        isMounted = false
      }
    }
  }, [context?.connected, context?.site, isChangingSite])

  // When site is selected and no project selected (or changing project), fetch projects
  useEffect(() => {
    if (!context?.connected || !context.site) return
    if (!context.project || isChangingProject) {
      let isMounted = true

      async function fetchProjects() {
        setLoadingProjects(true)
        try {
          const items = await getJiraProjects()
          if (isMounted) {
            setProjects(items)
            setSelectedProjectId(context.project?.id || context.project?.key || '')
          }
        } catch (err) {
          if (isMounted) setErrorMessage(normalizeJiraError(err))
        } finally {
          if (isMounted) setLoadingProjects(false)
        }
      }

      fetchProjects()
      return () => {
        isMounted = false
      }
    }
  }, [context?.connected, context?.site, context?.project, isChangingProject])

  // When project is selected and no board selected (or changing board), fetch boards
  useEffect(() => {
    if (!context?.connected || !context.site || !context.project) return
    if (!context.board || isChangingBoard) {
      let isMounted = true

      async function fetchBoards() {
        setLoadingBoards(true)
        try {
          const items = await getJiraBoards()
          if (isMounted) {
            // Strictly filter Scrum boards on the frontend as well
            const scrumOnly = items.filter(
              (b) => String(b.type || '').toLowerCase() === 'scrum',
            )
            setBoards(scrumOnly)
            setSelectedBoardId(context.board?.id ? String(context.board.id) : '')
          }
        } catch (err) {
          if (isMounted) setErrorMessage(normalizeJiraError(err))
        } finally {
          if (isMounted) setLoadingBoards(false)
        }
      }

      fetchBoards()
      return () => {
        isMounted = false
      }
    }
  }, [context?.connected, context?.site, context?.project, context?.board, isChangingBoard])

  // Actions
  async function handleConnect() {
    setConnecting(true)
    setErrorMessage(null)
    try {
      const res = await startJiraConnection()
      if (res?.authorization_url) {
        window.location.assign(res.authorization_url)
      } else {
        throw new Error('No authorization URL returned by Jira integration service')
      }
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
      setConnecting(false)
    }
  }

  async function handleConfirmDisconnect() {
    setDisconnecting(true)
    setShowDisconnectModal(false)
    setErrorMessage(null)
    try {
      await disconnectJira()
      setContext({ connected: false, site: null, project: null, board: null })
      setStatusInfo({ connected: false })
      setSites([])
      setProjects([])
      setBoards([])
      setSelectedSiteId('')
      setSelectedProjectId('')
      setSelectedBoardId('')
      setIsChangingSite(false)
      setIsChangingProject(false)
      setIsChangingBoard(false)
      setSuccessNotice('Jira Cloud disconnected successfully.')
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
    } finally {
      setDisconnecting(false)
    }
  }

  async function handleSelectSite(e) {
    e?.preventDefault?.()
    if (!selectedSiteId) return
    setSavingSite(true)
    setErrorMessage(null)
    try {
      await selectJiraSite(selectedSiteId)
      const freshContext = await getJiraContext()
      setContext(freshContext)
      setIsChangingSite(false)
      setIsChangingProject(false)
      setIsChangingBoard(false)
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
    } finally {
      setSavingSite(false)
    }
  }

  async function handleSelectProject(e) {
    e?.preventDefault?.()
    if (!selectedProjectId) return
    setSavingProject(true)
    setErrorMessage(null)
    try {
      const chosen = projects.find(
        (p) => String(p.id) === String(selectedProjectId) || p.key === selectedProjectId,
      )
      await selectJiraProject({
        projectId: chosen?.id || selectedProjectId,
        projectKey: chosen?.key || selectedProjectId,
      })
      const freshContext = await getJiraContext()
      setContext(freshContext)
      setIsChangingProject(false)
      setIsChangingBoard(false)
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
    } finally {
      setSavingProject(false)
    }
  }

  async function handleSelectBoard(e) {
    e?.preventDefault?.()
    if (!selectedBoardId) return
    setSavingBoard(true)
    setErrorMessage(null)
    try {
      await selectJiraBoard(Number(selectedBoardId))
      const freshContext = await getJiraContext()
      setContext(freshContext)
      setIsChangingBoard(false)
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
    } finally {
      setSavingBoard(false)
    }
  }

  if (loadingContext) {
    return (
      <Card className="mt-8 border-default bg-surface/50 p-6" data-testid="jira-integration-loading">
        <div className="flex items-center gap-3 text-content-secondary">
          <Spinner size="small" label="Checking Jira connection" />
          <span className="text-sm">Checking Jira connection status...</span>
        </div>
      </Card>
    )
  }

  const isConnected = Boolean(context?.connected || statusInfo?.connected)
  const isTargetReady = Boolean(
    isConnected && context?.site && context?.project && context?.board,
  )

  return (
    <section aria-labelledby="jira-integration-title" className="mt-8 space-y-4">
      {/* Notifications */}
      {successNotice && (
        <div
          role="status"
          className="flex items-center justify-between rounded-control border border-state-success/40 bg-state-success/10 p-3 text-xs text-state-success"
        >
          <span>{successNotice}</span>
          <button
            type="button"
            onClick={() => setSuccessNotice(null)}
            className="font-bold hover:underline"
            aria-label="Dismiss notice"
          >
            ×
          </button>
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="flex items-center justify-between rounded-control border border-state-danger/40 bg-state-danger/10 p-3 text-xs text-state-danger"
        >
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="font-bold hover:underline"
            aria-label="Dismiss alert"
          >
            ×
          </button>
        </div>
      )}

      <Card className="border-default bg-surface p-6 shadow-surface">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h3 id="jira-integration-title" className="text-lg font-semibold text-content-primary">
                Jira Cloud
              </h3>
              <StatusBadge
                label={isConnected ? 'Connected' : 'Not Connected'}
                tone={isConnected ? 'success' : 'neutral'}
              />
            </div>
            <p className="mt-1 text-xs text-content-secondary">
              Connect your Jira workspace to prepare this approved planning output{project?.name ? ` for ${project.name}` : ''} for synchronization.
            </p>
          </div>

          {isConnected && (
            <Button
              variant="outline"
              size="small"
              onClick={() => setShowDisconnectModal(true)}
              disabled={disconnecting}
              className="text-xs text-state-danger hover:border-state-danger hover:bg-state-danger/10"
            >
              Disconnect Jira
            </Button>
          )}
        </div>

        {/* Body based on connection state */}
        {!isConnected ? (
          <div className="mt-6 flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="max-w-xl text-sm text-content-muted">
              <p>
                Connect Jira to discover your authorized sites, software projects, and Scrum boards.
                No Jira issues or sprints will be created automatically.
              </p>
            </div>
            <Button
              variant="primary"
              onClick={handleConnect}
              loading={connecting}
              loadingLabel="Redirecting to Jira"
            >
              Connect Jira
            </Button>
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            {/* Hierarchy Progress & Target Selection */}
            <div className="grid gap-4 md:grid-cols-3">
              {/* Site Card */}
              <div className="rounded-control border border-default bg-elevated/50 p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-content-muted">
                  <span>1. JIRA SITE</span>
                  {context.site && !isChangingSite && (
                    <button
                      type="button"
                      onClick={() => setIsChangingSite(true)}
                      className="text-highlight hover:underline"
                    >
                      Change
                    </button>
                  )}
                </div>
                <div className="mt-2 text-sm">
                  {context.site && !isChangingSite ? (
                    <div>
                      <p className="font-semibold text-content-primary">{context.site.name}</p>
                      {context.site.url && (
                        <p className="truncate text-xs text-content-muted">{context.site.url}</p>
                      )}
                    </div>
                  ) : (
                    <span className="text-content-muted italic">Not selected</span>
                  )}
                </div>
              </div>

              {/* Project Card */}
              <div className="rounded-control border border-default bg-elevated/50 p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-content-muted">
                  <span>2. PROJECT</span>
                  {context.project && !isChangingProject && (
                    <button
                      type="button"
                      onClick={() => setIsChangingProject(true)}
                      className="text-highlight hover:underline"
                    >
                      Change
                    </button>
                  )}
                </div>
                <div className="mt-2 text-sm">
                  {context.project && !isChangingProject ? (
                    <div>
                      <p className="font-semibold text-content-primary">
                        <span className="font-mono text-highlight">{context.project.key}</span> —{' '}
                        {context.project.name}
                      </p>
                    </div>
                  ) : (
                    <span className="text-content-muted italic">Not selected</span>
                  )}
                </div>
              </div>

              {/* Board Card */}
              <div className="rounded-control border border-default bg-elevated/50 p-4">
                <div className="flex items-center justify-between text-xs font-semibold text-content-muted">
                  <span>3. SCRUM BOARD</span>
                  {context.board && !isChangingBoard && (
                    <button
                      type="button"
                      onClick={() => setIsChangingBoard(true)}
                      className="text-highlight hover:underline"
                    >
                      Change
                    </button>
                  )}
                </div>
                <div className="mt-2 text-sm">
                  {context.board && !isChangingBoard ? (
                    <div>
                      <p className="font-semibold text-content-primary">{context.board.name}</p>
                      <span className="text-xs uppercase text-highlight font-medium">Scrum</span>
                    </div>
                  ) : (
                    <span className="text-content-muted italic">Not selected</span>
                  )}
                </div>
              </div>
            </div>

            {/* Interactive Selectors based on hierarchy progress */}

            {/* Step 1: Site Selector */}
            {(!context.site || isChangingSite) && (
              <div className="rounded-control border border-accent-border/40 bg-surface/80 p-5">
                <h4 className="text-sm font-semibold text-content-primary">Select Jira Site</h4>
                <p className="mt-1 text-xs text-content-secondary">
                  Choose the Atlassian Jira Cloud workspace where planning will be synchronized.
                </p>

                {loadingSites ? (
                  <div className="mt-4 flex items-center gap-2 text-xs text-content-muted">
                    <Spinner size="small" label="Loading sites" />
                    <span>Loading authorized Jira sites...</span>
                  </div>
                ) : sites.length === 0 ? (
                  <p className="mt-4 text-xs text-content-muted italic">
                    No accessible Jira sites were found.
                  </p>
                ) : (
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                    <Select
                      id="jira-site-select"
                      label="Available Sites"
                      placeholder="Choose a Jira site..."
                      value={selectedSiteId}
                      onChange={(e) => setSelectedSiteId(e.target.value)}
                      options={sites.map((s) => ({
                        value: s.cloud_id,
                        label: `${s.name}${s.url ? ` (${s.url})` : ''}`,
                      }))}
                      disabled={savingSite}
                    />
                    <div className="flex items-center gap-2">
                      <Button
                        variant="primary"
                        onClick={handleSelectSite}
                        disabled={!selectedSiteId || savingSite}
                        loading={savingSite}
                        loadingLabel="Selecting Site"
                      >
                        Select Site
                      </Button>
                      {context.site && isChangingSite && (
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setIsChangingSite(false)
                            setSelectedSiteId(context.site.cloud_id)
                          }}
                          disabled={savingSite}
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Project Selector */}
            {context.site && !isChangingSite && (!context.project || isChangingProject) && (
              <div className="rounded-control border border-accent-border/40 bg-surface/80 p-5">
                <h4 className="text-sm font-semibold text-content-primary">Select Jira Project</h4>
                <p className="mt-1 text-xs text-content-secondary">
                  Choose an authorized Jira Software project on{' '}
                  <span className="font-semibold text-content-primary">{context.site.name}</span>.
                </p>

                {loadingProjects ? (
                  <div className="mt-4 flex items-center gap-2 text-xs text-content-muted">
                    <Spinner size="small" label="Loading projects" />
                    <span>Loading accessible Jira projects...</span>
                  </div>
                ) : projects.length === 0 ? (
                  <p className="mt-4 text-xs text-content-muted italic">
                    No accessible Jira projects were found.
                  </p>
                ) : (
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                    <Select
                      id="jira-project-select"
                      label="Available Projects"
                      placeholder="Choose a Jira project..."
                      value={selectedProjectId}
                      onChange={(e) => setSelectedProjectId(e.target.value)}
                      options={projects.map((p) => ({
                        value: p.id || p.key,
                        label: `${p.key} — ${p.name}`,
                      }))}
                      disabled={savingProject}
                    />
                    <div className="flex items-center gap-2">
                      <Button
                        variant="primary"
                        onClick={handleSelectProject}
                        disabled={!selectedProjectId || savingProject}
                        loading={savingProject}
                        loadingLabel="Selecting Project"
                      >
                        Select Project
                      </Button>
                      {context.project && isChangingProject && (
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setIsChangingProject(false)
                            setSelectedProjectId(context.project.id || context.project.key)
                          }}
                          disabled={savingProject}
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Step 3: Scrum Board Selector */}
            {context.site &&
              context.project &&
              !isChangingSite &&
              !isChangingProject &&
              (!context.board || isChangingBoard) && (
                <div className="rounded-control border border-accent-border/40 bg-surface/80 p-5">
                  <h4 className="text-sm font-semibold text-content-primary">Select Scrum Board</h4>
                  <p className="mt-1 text-xs text-content-secondary">
                    Select a Scrum board associated with project{' '}
                    <span className="font-semibold text-content-primary">
                      {context.project.key} — {context.project.name}
                    </span>
                    .
                  </p>

                  {loadingBoards ? (
                    <div className="mt-4 flex items-center gap-2 text-xs text-content-muted">
                      <Spinner size="small" label="Loading boards" />
                      <span>Loading Scrum boards...</span>
                    </div>
                  ) : boards.length === 0 ? (
                    <p className="mt-4 text-xs text-content-muted italic">
                      No Scrum boards were found for this project.
                    </p>
                  ) : (
                    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                      <Select
                        id="jira-board-select"
                        label="Available Scrum Boards"
                        placeholder="Choose a Scrum board..."
                        value={selectedBoardId}
                        onChange={(e) => setSelectedBoardId(e.target.value)}
                        options={boards.map((b) => ({
                          value: String(b.id),
                          label: `${b.name} (Scrum)`,
                        }))}
                        disabled={savingBoard}
                      />
                      <div className="flex items-center gap-2">
                        <Button
                          variant="primary"
                          onClick={handleSelectBoard}
                          disabled={!selectedBoardId || savingBoard}
                          loading={savingBoard}
                          loadingLabel="Selecting Board"
                        >
                          Select Board
                        </Button>
                        {context.board && isChangingBoard && (
                          <Button
                            variant="ghost"
                            onClick={() => {
                              setIsChangingBoard(false)
                              setSelectedBoardId(String(context.board.id))
                            }}
                            disabled={savingBoard}
                          >
                            Cancel
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

            {/* Target Ready State */}
            {isTargetReady && !isChangingSite && !isChangingProject && !isChangingBoard && (
              <div
                className="rounded-control border border-state-success/40 bg-state-success/10 p-4"
                data-testid="jira-target-ready"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-state-success">
                      Jira target is ready. No Jira data has been created or modified.
                    </h4>
                    <p className="mt-1 text-xs text-content-secondary">
                      Your synchronization target is configured for{' '}
                      <span className="font-semibold text-content-primary">
                        {context.site.name} / {context.project.key} / {context.board.name}
                      </span>
                      .
                    </p>
                  </div>
                  <StatusBadge label="Not Performed" tone="neutral" />
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3 pt-2">
                  <Button
                    variant="outline"
                    disabled={true}
                    aria-disabled="true"
                    title="Synchronization execution is not implemented in this phase"
                    className="cursor-not-allowed opacity-60 text-xs"
                  >
                    Sync Now (Preview Required)
                  </Button>
                  <span className="text-xs text-content-muted">
                    Human confirmation and sync preview will be required before any Jira items are created.
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Disconnect Confirmation Modal */}
      {showDisconnectModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="disconnect-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4"
          data-testid="jira-disconnect-modal"
        >
          <div className="w-full max-w-md rounded-panel border border-default bg-surface p-6 shadow-surface">
            <h3 id="disconnect-modal-title" className="text-base font-semibold text-content-primary">
              Disconnect Jira Cloud?
            </h3>
            <p className="mt-2 text-sm text-content-secondary">
              This removes the local integration connection and clears selected site, project, and board
              targets. Your Agent 2 planning results and generated JIRA_PLAN will remain unchanged.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <Button
                variant="outline"
                size="small"
                onClick={() => setShowDisconnectModal(false)}
                disabled={disconnecting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="small"
                onClick={handleConfirmDisconnect}
                loading={disconnecting}
                loadingLabel="Disconnecting"
              >
                Disconnect
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default JiraIntegrationSection
