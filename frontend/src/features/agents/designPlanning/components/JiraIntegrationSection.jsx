import { useEffect, useState } from 'react'
import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import Select from '../../../../components/ui/Select.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import Spinner from '../../../../components/ui/Spinner.jsx'
import {
  cleanJiraCallbackParams,
  disconnectJira,
  executeJiraSync,
  generateJiraSyncPreview,
  getJiraBoards,
  getJiraContext,
  getJiraIssueTypes,
  getJiraProjects,
  getJiraSites,
  getJiraStatus,
  getJiraSyncStatus,
  normalizeJiraError,
  selectJiraBoard,
  selectJiraProject,
  selectJiraSite,
  startJiraConnection,
  suggestIssueTypeMappings,
} from '../../../../services/jiraService.js'

function JiraIntegrationSection({ project, outputs = null, runId = null }) {
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

  // Issue Types and Mapping state
  const [loadingIssueTypes, setLoadingIssueTypes] = useState(false)
  const [issueTypes, setIssueTypes] = useState([])
  const [issueTypesError, setIssueTypesError] = useState(null)
  const [mappings, setMappings] = useState({
    EPIC: '',
    FEATURE: '',
    USER_STORY: '',
    TASK: '',
  })

  // Sync Preview state
  const [generatingPreview, setGeneratingPreview] = useState(false)
  const [previewData, setPreviewData] = useState(null)
  const [previewError, setPreviewError] = useState(null)

  // Synchronization execution state (Prompt 7B)
  const [showSyncConfirmModal, setShowSyncConfirmModal] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [syncError, setSyncError] = useState(null)

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

  // Auto-refresh connection status when user returns to this tab after authorizing in a new tab
  useEffect(() => {
    if (context?.connected) return
    let isMounted = true

    async function checkConnectionOnFocus() {
      try {
        const [freshContext, freshStatus] = await Promise.all([
          getJiraContext(),
          getJiraStatus(),
        ])
        if (!isMounted) return
        if (freshContext?.connected) {
          setContext(freshContext)
          setStatusInfo(freshStatus)
          setSuccessNotice('Jira Cloud authorized successfully!')
        }
      } catch {
        // Silently ignore background refresh errors
      }
    }

    window.addEventListener('focus', checkConnectionOnFocus)
    return () => {
      isMounted = false
      window.removeEventListener('focus', checkConnectionOnFocus)
    }
  }, [context?.connected])

  // Check for any existing synchronization record for this run
  useEffect(() => {
    let isMounted = true
    async function loadSyncStatus() {
      const effectiveProjectId = project?.agent_project_id || project?.id
      const effectiveRunId = runId || project?.run_id
      if (!effectiveProjectId || !effectiveRunId) return

      try {
        const existing = await getJiraSyncStatus({
          agent_project_id: effectiveProjectId,
          run_id: effectiveRunId,
        })
        if (isMounted && existing && existing.status && existing.status !== 'NOT_PERFORMED') {
          setSyncResult(existing)
        }
      } catch {
        // Ignore initial status lookup errors
      }
    }
    loadSyncStatus()
    return () => {
      isMounted = false
    }
  }, [project?.agent_project_id, project?.id, runId, project?.run_id])

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
        window.open(res.authorization_url, '_blank', 'noopener,noreferrer')
      } else {
        throw new Error('No authorization URL returned by Jira integration service')
      }
    } catch (err) {
      setErrorMessage(normalizeJiraError(err))
    } finally {
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

  const isConnected = Boolean(context?.connected || statusInfo?.connected)
  const isTargetReady = Boolean(
    isConnected && context?.site && context?.project && context?.board,
  )

  // Load available issue types when target becomes ready
  useEffect(() => {
    if (!isTargetReady || isChangingSite || isChangingProject || isChangingBoard) return

    let isMounted = true

    async function loadTypes() {
      try {
        setLoadingIssueTypes(true)
        setIssueTypesError(null)
        const types = await getJiraIssueTypes()
        if (!isMounted) return
        setIssueTypes(types || [])
        const suggestions = suggestIssueTypeMappings(types || [])
        setMappings(suggestions)
      } catch (err) {
        if (!isMounted) return
        setIssueTypesError(normalizeJiraError(err))
      } finally {
        if (isMounted) setLoadingIssueTypes(false)
      }
    }

    loadTypes()

    return () => {
      isMounted = false
    }
  }, [
    isTargetReady,
    context?.site?.cloud_id,
    context?.project?.id,
    context?.project?.key,
    context?.board?.id,
    isChangingSite,
    isChangingProject,
    isChangingBoard,
  ])

  const isMappingComplete = Boolean(
    mappings.EPIC &&
    mappings.FEATURE &&
    mappings.USER_STORY &&
    mappings.TASK,
  )

  async function handleGeneratePreview() {
    setGeneratingPreview(true)
    setPreviewError(null)
    try {
      const payload = {
        agent_project_id: project?.agent_project_id || project?.id,
        run_id: runId || project?.run_id || null,
        mappings,
        outputs: outputs || project?.outputs || null,
      }
      const data = await generateJiraSyncPreview(payload)
      setPreviewData(data)
    } catch (err) {
      setPreviewError(normalizeJiraError(err))
    } finally {
      setGeneratingPreview(false)
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
              loadingLabel="Opening Jira..."
            >
              Connect Jira
              <svg
                aria-hidden="true"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
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
              <>
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

                {/* Issue Type Mapping Section */}
                <div
                  className="rounded-control border border-default bg-surface/90 p-5 space-y-4"
                  data-testid="jira-issue-type-mapping"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-default pb-3">
                    <div>
                      <h4 className="text-sm font-semibold text-content-primary">
                        Issue Type Mapping
                      </h4>
                      <p className="mt-0.5 text-xs text-content-secondary">
                        Map AgileFlow planning hierarchy types to Jira issue types available in{' '}
                        <span className="font-semibold text-content-primary">
                          {context.project.key} — {context.project.name}
                        </span>
                        .
                      </p>
                    </div>
                    <span className="text-xs text-content-muted">Human review required</span>
                  </div>

                  {loadingIssueTypes ? (
                    <div className="flex items-center gap-2 py-4 text-xs text-content-muted">
                      <Spinner size="small" label="Loading Jira issue types" />
                      <span>Loading available Jira issue types for {context.project.key}...</span>
                    </div>
                  ) : issueTypesError ? (
                    <div className="space-y-2">
                      <div className="rounded-control border border-state-danger/40 bg-state-danger/10 p-3 text-xs text-state-danger">
                        {issueTypesError}
                      </div>
                      <Button
                        variant="outline"
                        size="small"
                        onClick={() => {
                          setLoadingIssueTypes(true)
                          setIssueTypesError(null)
                          getJiraIssueTypes()
                            .then((types) => {
                              setIssueTypes(types || [])
                              const suggestions = suggestIssueTypeMappings(types || [])
                              setMappings(suggestions)
                            })
                            .catch((err) => setIssueTypesError(normalizeJiraError(err)))
                            .finally(() => setLoadingIssueTypes(false))
                        }}
                      >
                        Retry Loading Issue Types
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Notice if Feature is unmapped */}
                      {!mappings.FEATURE && (
                        <div className="rounded-control border border-state-warning/30 bg-state-warning/10 p-3 text-xs text-state-warning">
                          <span className="font-semibold">Feature issue type:</span> Project{' '}
                          {context.project.key} does not have an exact &ldquo;Feature&rdquo; issue type.
                          Please select a compatible Jira issue type (e.g. Story or Task) to proceed.
                        </div>
                      )}

                      {/* Mappings Grid */}
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {/* Epic */}
                        <div>
                          <Select
                            id="jira-mapping-epic"
                            label="Epic"
                            placeholder="Select issue type..."
                            value={mappings.EPIC}
                            onChange={(e) =>
                              setMappings((prev) => ({ ...prev, EPIC: e.target.value }))
                            }
                            options={issueTypes.map((t) => ({
                              value: t.name,
                              label: `${t.name}${t.subtask ? ' (Subtask)' : ''}`,
                            }))}
                            helperText="AgileFlow Epic"
                          />
                        </div>

                        {/* Feature */}
                        <div>
                          <Select
                            id="jira-mapping-feature"
                            label="Feature"
                            placeholder="Select compatible type..."
                            value={mappings.FEATURE}
                            onChange={(e) =>
                              setMappings((prev) => ({ ...prev, FEATURE: e.target.value }))
                            }
                            options={issueTypes.map((t) => ({
                              value: t.name,
                              label: `${t.name}${t.subtask ? ' (Subtask)' : ''}`,
                            }))}
                            helperText={
                              !mappings.FEATURE
                                ? 'Required: select compatible Jira type'
                                : 'AgileFlow Feature'
                            }
                            error={!mappings.FEATURE ? 'Mapping required' : undefined}
                          />
                        </div>

                        {/* User Story */}
                        <div>
                          <Select
                            id="jira-mapping-user-story"
                            label="User Story"
                            placeholder="Select issue type..."
                            value={mappings.USER_STORY}
                            onChange={(e) =>
                              setMappings((prev) => ({ ...prev, USER_STORY: e.target.value }))
                            }
                            options={issueTypes.map((t) => ({
                              value: t.name,
                              label: `${t.name}${t.subtask ? ' (Subtask)' : ''}`,
                            }))}
                            helperText="AgileFlow User Story"
                          />
                        </div>

                        {/* Task */}
                        <div>
                          <Select
                            id="jira-mapping-task"
                            label="Task"
                            placeholder="Select issue type..."
                            value={mappings.TASK}
                            onChange={(e) =>
                              setMappings((prev) => ({ ...prev, TASK: e.target.value }))
                            }
                            options={issueTypes.map((t) => ({
                              value: t.name,
                              label: `${t.name}${t.subtask ? ' (Subtask)' : ''}`,
                            }))}
                            helperText="AgileFlow Task"
                          />
                        </div>
                      </div>

                      {/* Action Bar */}
                      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default pt-3">
                        <div className="text-xs text-content-muted">
                          {!isMappingComplete ? (
                            <span className="text-state-warning">
                              Map all 4 AgileFlow types to enable sync preview.
                            </span>
                          ) : (
                            <span className="text-state-success">
                              All types mapped. Ready to generate preview.
                            </span>
                          )}
                        </div>
                        <Button
                          variant="primary"
                          onClick={handleGeneratePreview}
                          disabled={!isMappingComplete || generatingPreview}
                          loading={generatingPreview}
                          loadingLabel="Generating Preview"
                          id="generate-sync-preview-btn"
                        >
                          {previewData ? 'Regenerate Sync Preview' : 'Generate Sync Preview'}
                        </Button>
                      </div>

                      {previewError && (
                        <div
                          role="alert"
                          className="rounded-control border border-state-danger/40 bg-state-danger/10 p-3 text-xs text-state-danger"
                        >
                          {previewError}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Sync Preview View */}
                {previewData && (
                  <div
                    className="rounded-control border border-accent-border/40 bg-surface/95 p-5 space-y-6"
                    data-testid="jira-sync-preview"
                  >
                    {/* Header */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-default pb-4">
                      <div>
                        <div className="flex items-center gap-3">
                          <h4 className="text-base font-semibold text-content-primary">
                            Jira Synchronization Preview
                          </h4>
                          <StatusBadge label="Synchronization: NOT PERFORMED" tone="neutral" />
                        </div>
                        <p className="mt-1 text-xs font-semibold text-state-warning">
                          No Jira data has been created or modified.
                        </p>
                      </div>
                      <span className="text-xs text-content-muted">Zero Jira writes</span>
                    </div>

                    {/* Target Site / Project / Board */}
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 rounded-control border border-default/60 bg-surface-secondary/40 p-3 text-xs">
                      <div>
                        <span className="text-content-muted block">Target Site</span>
                        <span className="font-medium text-content-primary">
                          {previewData.target?.site?.name || '—'}
                        </span>
                        {previewData.target?.site?.url && (
                          <span className="text-content-muted block text-[11px] truncate">
                            {previewData.target.site.url}
                          </span>
                        )}
                      </div>
                      <div>
                        <span className="text-content-muted block">Project</span>
                        <span className="font-medium text-content-primary">
                          {previewData.target?.project?.key} — {previewData.target?.project?.name}
                        </span>
                      </div>
                      <div>
                        <span className="text-content-muted block">Scrum Board</span>
                        <span className="font-medium text-content-primary">
                          {previewData.target?.board?.name}
                        </span>
                      </div>
                    </div>

                    {/* Summary Metrics */}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <div className="rounded-control border border-default bg-surface p-3 text-center">
                        <div className="text-xl font-bold text-content-primary">
                          {previewData.summary?.total_sprints ?? 0}
                        </div>
                        <div className="text-xs text-content-secondary">Sprints</div>
                      </div>
                      <div className="rounded-control border border-default bg-surface p-3 text-center">
                        <div className="text-xl font-bold text-content-primary">
                          {previewData.summary?.total_issues ?? 0}
                        </div>
                        <div className="text-xs text-content-secondary">Total Issues</div>
                      </div>
                      <div className="rounded-control border border-default bg-surface p-3 text-center">
                        <div className="text-xl font-bold text-content-primary">
                          {previewData.summary?.total_points ?? 0}
                        </div>
                        <div className="text-xs text-content-secondary">Story Points</div>
                      </div>
                      <div className="rounded-control border border-default bg-surface p-3 text-center">
                        <div className="text-xs text-content-secondary space-y-0.5">
                          <div>
                            Epics:{' '}
                            <span className="font-semibold text-content-primary">
                              {previewData.summary?.epic_count ?? 0}
                            </span>
                          </div>
                          <div>
                            Features:{' '}
                            <span className="font-semibold text-content-primary">
                              {previewData.summary?.feature_count ?? 0}
                            </span>
                          </div>
                          <div>
                            Stories:{' '}
                            <span className="font-semibold text-content-primary">
                              {previewData.summary?.story_count ?? 0}
                            </span>
                          </div>
                          <div>
                            Tasks:{' '}
                            <span className="font-semibold text-content-primary">
                              {previewData.summary?.task_count ?? 0}
                            </span>
                          </div>
                        </div>
                        <div className="text-[11px] text-content-muted mt-1">Breakdown</div>
                      </div>
                    </div>

                    {/* Warnings */}
                    {previewData.warnings && previewData.warnings.length > 0 && (
                      <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-3 text-xs text-state-warning space-y-1">
                        <div className="font-semibold">Preview Warnings:</div>
                        <ul className="list-disc pl-4 space-y-0.5">
                          {previewData.warnings.map((w, idx) => (
                            <li key={idx}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Applied Issue Type Mappings */}
                    <div className="rounded-control border border-default/60 bg-surface p-3">
                      <div className="text-xs font-semibold text-content-primary mb-2">
                        Applied Issue Type Mappings
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="text-content-muted">Epic →</span>
                          <span className="font-medium text-content-primary">
                            {previewData.mappings?.EPIC}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-content-muted">Feature →</span>
                          <span className="font-medium text-content-primary">
                            {previewData.mappings?.FEATURE}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-content-muted">User Story →</span>
                          <span className="font-medium text-content-primary">
                            {previewData.mappings?.USER_STORY}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-content-muted">Task →</span>
                          <span className="font-medium text-content-primary">
                            {previewData.mappings?.TASK}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Generated Sprints Preview */}
                    {previewData.sprints && previewData.sprints.length > 0 && (
                      <div className="space-y-2">
                        <h5 className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                          Planned Sprints ({previewData.sprints.length})
                        </h5>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                          {previewData.sprints.map((s) => (
                            <div
                              key={s.id}
                              className="rounded-control border border-default bg-surface p-3 text-xs space-y-1"
                            >
                              <div className="font-semibold text-content-primary">{s.name}</div>
                              <div className="flex items-center justify-between text-content-secondary">
                                <span>{s.planned_points} pts planned</span>
                                <span>{s.duration_days} days</span>
                              </div>
                              {s.start_date && s.end_date && (
                                <div className="text-[11px] text-content-muted">
                                  {s.start_date} → {s.end_date}
                                </div>
                              )}
                              <div className="text-[11px] text-content-muted">
                                {s.item_count} items assigned
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Preview Issues Table */}
                    <div className="space-y-2">
                      <h5 className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                        Preview Issues ({previewData.issues?.length ?? 0})
                      </h5>
                      <div className="overflow-x-auto rounded-control border border-default bg-surface">
                        <table className="w-full text-left text-xs">
                          <thead className="border-b border-default bg-surface-secondary/50 text-content-muted">
                            <tr>
                              <th className="px-3 py-2 font-medium">Artifact ID</th>
                              <th className="px-3 py-2 font-medium">Mapped Jira Type</th>
                              <th className="px-3 py-2 font-medium">Summary</th>
                              <th className="px-3 py-2 font-medium">Planned Sprint</th>
                              <th className="px-3 py-2 font-medium">Parent</th>
                              <th className="px-3 py-2 font-medium">Points</th>
                              <th className="px-3 py-2 font-medium">Assignee</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-default/40">
                            {(previewData.issues || []).map((issue, idx) => (
                              <tr key={issue.artifact_id || issue.id || idx} className="hover:bg-surface-secondary/30">
                                <td className="px-3 py-2 font-mono text-[11px] font-semibold text-content-primary whitespace-nowrap">
                                  {issue.artifact_id}
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap">
                                  <span className="inline-block rounded bg-surface-secondary px-1.5 py-0.5 text-[11px] text-content-primary font-medium">
                                    {issue.jira_issue_type}
                                  </span>
                                </td>
                                <td
                                  className="px-3 py-2 text-content-primary max-w-xs truncate"
                                  title={issue.summary}
                                >
                                  {issue.summary}
                                </td>
                                <td className="px-3 py-2 text-content-secondary whitespace-nowrap">
                                  {issue.planned_sprint || (
                                    <span className="text-content-muted italic">Backlog</span>
                                  )}
                                </td>
                                <td className="px-3 py-2 font-mono text-[11px] text-content-muted whitespace-nowrap">
                                  {issue.parent_id || '—'}
                                </td>
                                <td className="px-3 py-2 text-content-secondary whitespace-nowrap">
                                  {issue.estimate_points != null
                                    ? `${issue.estimate_points} pts`
                                    : '—'}
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap">
                                  <span className="inline-flex items-center rounded bg-surface-secondary/80 px-2 py-0.5 text-[11px] text-content-muted font-medium">
                                    Unassigned
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Sync Action Area: Prompt 7B Hard HITL Confirmation Flow */}
                    {!syncResult && !syncing && (
                      <div
                        className="rounded-control border border-state-neutral/30 bg-surface-secondary/40 p-3 text-xs text-content-secondary flex flex-wrap items-center justify-between gap-3"
                        data-testid="jira-sync-action-area"
                      >
                        <div>
                          <span className="font-semibold text-content-primary">
                            Synchronization: NOT PERFORMED.
                          </span>{' '}
                          <span>No Jira data has been created or modified yet.</span>
                        </div>
                        <Button
                          variant="primary"
                          size="small"
                          onClick={() => {
                            setSyncError(null)
                            setShowSyncConfirmModal(true)
                          }}
                          disabled={syncing}
                          data-testid="start-sync-btn"
                        >
                          Synchronize with Jira
                        </Button>
                      </div>
                    )}

                    {/* Syncing In Progress Indicator */}
                    {syncing && (
                      <div
                        className="rounded-control border border-brand/40 bg-brand/10 p-4 text-xs text-content-primary flex items-center justify-between gap-3"
                        data-testid="jira-sync-in-progress"
                      >
                        <div className="flex items-center gap-3">
                          <Spinner size="small" />
                          <div>
                            <span className="font-semibold">Synchronization IN PROGRESS...</span>
                            <p className="text-content-secondary text-[11px] mt-0.5">
                              Creating Jira sprints, unassigned issues, and placing planned work.
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          size="small"
                          disabled={true}
                          className="opacity-60 cursor-not-allowed text-xs"
                        >
                          Synchronizing...
                        </Button>
                      </div>
                    )}

                    {/* Sync Error Banner if any */}
                    {syncError && !syncing && (
                      <div className="rounded-control border border-state-danger/40 bg-state-danger/10 p-3 text-xs text-state-danger flex items-center justify-between gap-2">
                        <span>{syncError}</span>
                        <Button
                          variant="ghost"
                          size="small"
                          onClick={() => setSyncError(null)}
                          className="text-xs text-content-muted"
                        >
                          Dismiss
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {/* Synchronization Results Card */}
                {syncResult && (
                  <div
                    className="rounded-control border border-default bg-surface p-4 space-y-4"
                    data-testid="jira-sync-result-card"
                  >
                    {/* Header with status badge */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-default">
                      <div className="flex items-center gap-2">
                        <StatusBadge
                          label={syncResult.status}
                          tone={
                            syncResult.status === 'COMPLETED'
                              ? 'success'
                              : syncResult.status === 'PARTIAL'
                              ? 'warning'
                              : 'danger'
                          }
                        />
                            <span className="font-semibold text-sm text-content-primary">
                              {syncResult.status === 'COMPLETED' && 'Jira synchronization completed.'}
                              {syncResult.status === 'PARTIAL' &&
                                'Jira synchronization partially completed. Review failed items before retrying.'}
                              {syncResult.status === 'FAILED' &&
                                'Jira synchronization failed. Your Agent 2 generated results are unchanged.'}
                            </span>
                          </div>

                          {(syncResult.status === 'PARTIAL' || syncResult.status === 'FAILED') && (
                            <Button
                              variant="primary"
                              size="small"
                              onClick={() => {
                                setSyncError(null)
                                setShowSyncConfirmModal(true)
                              }}
                              disabled={syncing}
                              data-testid="retry-sync-btn"
                            >
                              {syncResult.status === 'PARTIAL'
                                ? 'Resume Synchronization'
                                : 'Retry Synchronization'}
                            </Button>
                          )}
                        </div>

                        {/* Summary Metrics Grid */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div className="rounded border border-default bg-surface-secondary/50 p-3">
                            <div className="text-[11px] text-content-muted uppercase tracking-wider font-semibold">
                              Sprints
                            </div>
                            <div className="mt-1 text-sm font-semibold text-content-primary">
                              {syncResult.sprint_summary?.created ?? 0} created
                              {(syncResult.sprint_summary?.reused ?? 0) > 0 &&
                                ` (${syncResult.sprint_summary.reused} reused)`}
                            </div>
                            {(syncResult.sprint_summary?.failed ?? 0) > 0 && (
                              <div className="text-xs text-state-danger font-medium mt-0.5">
                                {syncResult.sprint_summary.failed} failed
                              </div>
                            )}
                          </div>

                          <div className="rounded border border-default bg-surface-secondary/50 p-3">
                            <div className="text-[11px] text-content-muted uppercase tracking-wider font-semibold">
                              Issues (Unassigned)
                            </div>
                            <div className="mt-1 text-sm font-semibold text-content-primary">
                              {syncResult.issue_summary?.created ?? 0} created
                              {(syncResult.issue_summary?.reused ?? 0) > 0 &&
                                ` (${syncResult.issue_summary.reused} reused)`}
                            </div>
                            {(syncResult.issue_summary?.failed ?? 0) > 0 && (
                              <div className="text-xs text-state-danger font-medium mt-0.5">
                                {syncResult.issue_summary.failed} failed
                              </div>
                            )}
                          </div>

                          <div className="rounded border border-default bg-surface-secondary/50 p-3">
                            <div className="text-[11px] text-content-muted uppercase tracking-wider font-semibold">
                              Sprint Placements
                            </div>
                            <div className="mt-1 text-sm font-semibold text-content-primary">
                              {syncResult.placement_summary?.created ?? 0} placed
                            </div>
                            {(syncResult.placement_summary?.failed ?? 0) > 0 && (
                              <div className="text-xs text-state-danger font-medium mt-0.5">
                                {syncResult.placement_summary.failed} failed
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Failures List if any */}
                        {syncResult.failures && syncResult.failures.length > 0 && (
                          <div
                            className="rounded border border-state-danger/40 bg-state-danger/10 p-3 space-y-1.5 text-xs text-content-primary"
                            data-testid="sync-failures-list"
                          >
                            <div className="font-semibold text-state-danger">
                              Failed Items ({syncResult.failures.length}):
                            </div>
                            <ul className="list-disc list-inside space-y-1 text-content-secondary">
                              {syncResult.failures.map((fail, idx) => (
                                <li key={idx}>
                                  <span className="font-mono text-content-primary">
                                    [{fail.entity_type}] {fail.entity_id}:
                                  </span>{' '}
                                  {fail.error}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Warnings if any */}
                        {syncResult.warnings && syncResult.warnings.length > 0 && (
                          <div className="rounded border border-state-warning/40 bg-state-warning/10 p-3 space-y-1.5 text-xs text-content-primary">
                            <div className="font-semibold text-state-warning">Warnings:</div>
                            <ul className="list-disc list-inside space-y-1 text-content-secondary">
                              {syncResult.warnings.map((warn, idx) => (
                                <li key={idx}>{warn}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Traceability Table */}
                        {syncResult.traceability?.issues &&
                          syncResult.traceability.issues.length > 0 && (
                            <div className="space-y-2 pt-1" data-testid="sync-traceability-section">
                              <div className="text-xs font-semibold text-content-primary">
                                Traceability & Created Jira Keys
                              </div>
                              <div className="overflow-x-auto rounded border border-default">
                                <table className="w-full text-left text-xs border-collapse">
                                  <thead>
                                    <tr className="border-b border-default bg-surface-secondary/60 text-content-muted">
                                      <th className="p-2 font-medium">AgileFlow ID</th>
                                      <th className="p-2 font-medium">Jira Key</th>
                                      <th className="p-2 font-medium">Type</th>
                                      <th className="p-2 font-medium">Summary</th>
                                      <th className="p-2 font-medium">Sprint</th>
                                      <th className="p-2 font-medium">Parent Key</th>
                                      <th className="p-2 font-medium">Assignee</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-default">
                                    {syncResult.traceability.issues.map((iss) => (
                                      <tr
                                        key={iss.artifact_id}
                                        className="hover:bg-surface-secondary/30"
                                      >
                                        <td className="p-2 font-mono text-content-primary">
                                          {iss.artifact_id}
                                        </td>
                                        <td className="p-2 font-mono font-semibold">
                                          {iss.browse_url ? (
                                            <a
                                              href={iss.browse_url}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              className="text-brand hover:underline inline-flex items-center gap-1"
                                            >
                                              {iss.jira_key} ↗
                                            </a>
                                          ) : (
                                            iss.jira_key
                                          )}
                                        </td>
                                        <td className="p-2 text-content-secondary">
                                          {iss.jira_issue_type}
                                        </td>
                                        <td
                                          className="p-2 text-content-primary max-w-xs truncate"
                                          title={iss.summary}
                                        >
                                          {iss.summary}
                                        </td>
                                        <td className="p-2 text-content-secondary">
                                          {iss.planned_sprint || '—'}
                                        </td>
                                        <td className="p-2 font-mono text-content-muted">
                                          {iss.parent_jira_key || '—'}
                                        </td>
                                        <td className="p-2 text-content-muted italic">
                                          Unassigned
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}
                      </div>
                    )}
              </>
            )}
          </div>
        )}
      </Card>

      {/* Synchronization Confirmation Modal (Prompt 7B Hard HITL Boundary) */}
      {showSyncConfirmModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="sync-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4"
          data-testid="jira-sync-confirm-modal"
        >
          <div className="w-full max-w-md rounded-panel border border-default bg-surface p-6 shadow-surface space-y-4">
            <h3 id="sync-modal-title" className="text-base font-semibold text-content-primary">
              Synchronize this approved plan with Jira?
            </h3>
            <p className="text-sm text-content-secondary leading-relaxed">
              This will create{' '}
              <strong className="text-content-primary font-semibold">
                {previewData?.summary?.total_sprints ?? previewData?.sprints?.length ?? 0} sprints
              </strong>{' '}
              and{' '}
              <strong className="text-content-primary font-semibold">
                {previewData?.summary?.total_issues ?? previewData?.issues?.length ?? 0} Jira issues
              </strong>{' '}
              in{' '}
              <strong className="text-content-primary font-semibold">
                {context?.project?.name || context?.project?.key || 'the selected project'}
              </strong>
              {context?.board ? ` (${context.board.name})` : ''}.
            </p>
            <div className="rounded-control border border-state-neutral/40 bg-surface-secondary/50 p-3 text-xs text-content-secondary">
              <span className="font-semibold text-content-primary">Notice:</span> Issues will remain unassigned. You can assign developers manually in Jira later.
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="small"
                onClick={() => setShowSyncConfirmModal(false)}
                disabled={syncing}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="small"
                onClick={async () => {
                  setShowSyncConfirmModal(false)
                  setSyncing(true)
                  setSyncError(null)

                  try {
                    const effectiveProjectId = project?.agent_project_id || project?.id
                    const effectiveRunId = runId || project?.run_id

                    const result = await executeJiraSync({
                      agent_project_id: effectiveProjectId,
                      run_id: effectiveRunId,
                      mappings,
                      confirmation: true,
                      outputs,
                    })
                    setSyncResult(result)
                    if (result.status === 'COMPLETED') {
                      setSuccessNotice('Jira synchronization completed successfully!')
                    } else if (result.status === 'PARTIAL') {
                      setErrorMessage(
                        'Jira synchronization partially completed. Review failed items before retrying.',
                      )
                    } else if (result.status === 'FAILED') {
                      setErrorMessage(
                        'Jira synchronization failed. Your Agent 2 generated results are unchanged.',
                      )
                    }
                  } catch (err) {
                    const normalized = normalizeJiraError(err)
                    setSyncError(normalized)
                    setErrorMessage(normalized)
                  } finally {
                    setSyncing(false)
                  }
                }}
                loading={syncing}
                loadingLabel="Synchronizing..."
                data-testid="confirm-sync-btn"
              >
                Confirm Synchronization
              </Button>
            </div>
          </div>
        </div>
      )}

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
