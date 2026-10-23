import { useCallback, useMemo, useState } from 'react'

import ValidationTraceabilityHistory from '../../../../components/agents/agent-2/results/ValidationTraceabilityHistory.jsx'
import Button from '../../../../components/ui/Button.jsx'
import { getAgentProjectRun } from '../../../../services/agentProjectService.js'
import { formatDateTime } from '../../../../utils/dateTime.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

function formatRunDate(value) {
  if (!value) return 'Not recorded'
  const formatted = formatDateTime(value)
  return formatted || value
}

export default function ValidationTraceabilityPanel({
  project,
  runResult,
  runState = 'idle',
  runError = '',
  runs = [],
  selectedRunId: externalSelectedRunId,
  selectedRunData: externalSelectedRunData,
  onSelectRun: externalOnSelectRun,
  onViewRun,
  onNavigate,
}) {
  const [internalSelectedRunId, setInternalSelectedRunId] = useState(null)
  const [fetchedRunData, setFetchedRunData] = useState(null)
  const [loadingHistoricalRun, setLoadingHistoricalRun] = useState(false)
  const [historicalRunError, setHistoricalRunError] = useState(null)

  const selectedHistoricalRunId = externalSelectedRunId !== undefined ? externalSelectedRunId : internalSelectedRunId

  const effectiveRuns = useMemo(() => {
    return Array.isArray(runs) ? runs : []
  }, [runs])

  const projectId = project?.agent_project_id || project?.id

  const cachedRun = useMemo(() => {
    if (!selectedHistoricalRunId) return null
    return effectiveRuns.find((r) => r.run_id === selectedHistoricalRunId) || null
  }, [effectiveRuns, selectedHistoricalRunId])

  const historicalRunData = useMemo(() => {
    if (externalSelectedRunData && externalSelectedRunData.run_id === selectedHistoricalRunId) {
      return externalSelectedRunData
    }
    if (!selectedHistoricalRunId) return null
    if (cachedRun?.output_manifest && typeof cachedRun.output_manifest === 'object' && Object.keys(cachedRun.output_manifest).length > 0) {
      return cachedRun
    }
    return fetchedRunData || cachedRun
  }, [cachedRun, externalSelectedRunData, fetchedRunData, selectedHistoricalRunId])

  const handleOpenHistoricalRun = useCallback(
    (targetRunId) => {
      if (externalOnSelectRun) {
        externalOnSelectRun(targetRunId)
      } else {
        setInternalSelectedRunId(targetRunId)
      }
      setFetchedRunData(null)
      const cached = effectiveRuns.find((r) => r.run_id === targetRunId)
      if (cached?.output_manifest && typeof cached.output_manifest === 'object' && Object.keys(cached.output_manifest).length > 0) {
        setFetchedRunData(cached)
      } else if (projectId) {
        setLoadingHistoricalRun(true)
        setHistoricalRunError(null)
        Promise.resolve()
          .then(() => getAgentProjectRun(projectId, targetRunId))
          .then((res) => {
            if (res?.data) {
              setFetchedRunData(res.data)
            }
          })
          .catch((err) => {
            setHistoricalRunError(err?.message || 'Failed to load historical run details.')
          })
          .finally(() => {
            setLoadingHistoricalRun(false)
          })
      }
      if (onViewRun) {
        onViewRun(targetRunId)
      }
    },
    [effectiveRuns, externalOnSelectRun, onViewRun, projectId],
  )

  const handleBackToOverview = useCallback(() => {
    if (externalOnSelectRun) {
      externalOnSelectRun(null)
    } else {
      setInternalSelectedRunId(null)
    }
    setFetchedRunData(null)
  }, [externalOnSelectRun])

  // Determine what run is being viewed
  const hasActiveSessionRun = Boolean(runResult) || runState === 'completed' || runState === 'failed'
  const isViewingHistoricalRun = Boolean(selectedHistoricalRunId)

  return (
    <div className="space-y-6" data-testid="agent2-panel-VALIDATION_TRACEABILITY">
      {/* Historical run selection banner when inspecting a historical run */}
      {isViewingHistoricalRun && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-panel border border-state-info/40 bg-state-info-soft p-3 text-xs text-content-primary">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-state-info" aria-hidden="true" />
            <span>
              Inspecting historical run <strong className="font-mono">{selectedHistoricalRunId}</strong> — persisted outputs only; no regeneration.
            </span>
          </div>
          <div className="flex items-center gap-2">
            {onNavigate && (
              <Button
                variant="outline"
                size="small"
                onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}
              >
                View Planning Results (Node 7) →
              </Button>
            )}
            <Button variant="ghost" size="small" onClick={handleBackToOverview}>
              ← Back to current view
            </Button>
          </div>
        </div>
      )}

      {loadingHistoricalRun && (
        <div className="rounded-panel border border-default bg-surface p-4 text-center text-xs text-content-secondary">
          Loading historical run details...
        </div>
      )}

      {historicalRunError && (
        <div className="rounded-panel border border-state-danger/40 bg-state-danger-soft p-3 text-xs text-state-danger">
          {historicalRunError}
        </div>
      )}

      {/* Case 1: Viewing a specific historical run */}
      {isViewingHistoricalRun && historicalRunData ? (
        <div className="space-y-4">
          <ValidationTraceabilityHistory
            run={historicalRunData}
            status={historicalRunData.status}
            outputs={historicalRunData.output_manifest || historicalRunData.outputs || {}}
            correction_attempts={historicalRunData.correction_attempts}
            isHistorical={true}
            project={project}
            runs={effectiveRuns}
            onViewRun={handleOpenHistoricalRun}
            onBackToOverview={handleBackToOverview}
          />
        </div>
      ) : hasActiveSessionRun ? (
        /* Case 2: Viewing active session run results */
        <ValidationTraceabilityHistory
          result={runResult}
          status={runResult?.status || (runState === 'failed' ? 'FAILED' : 'COMPLETED')}
          outputs={runResult?.outputs || {}}
          errors={!runResult?.errors?.length && runError ? [{ message: runError }] : undefined}
          correction_attempts={runResult?.correction_attempts}
          project={project}
          runs={effectiveRuns}
          onViewRun={handleOpenHistoricalRun}
        />
      ) : (
        /* Case 3: No active session run and no historical run selected yet */
        <div className="space-y-6">
          {/* Breadcrumb row */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-content-muted">
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-content-secondary">{project?.name || 'Project'}</span>
              <span className="text-content-muted">/</span>
              <span>Standalone Agent 2</span>
            </div>
            <div className="flex items-center gap-2">
              <span>Standalone demo</span>
              <span className="text-content-muted">•</span>
              <span className="flex items-center gap-1.5 text-content-secondary">
                <span className="inline-block h-2 w-2 rounded-full bg-content-primary" aria-hidden="true" />
                Human reviewer
              </span>
            </div>
          </div>

          {/* Header row */}
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
            <div>
              <h2 id="validation-history-title" className="text-page-heading font-semibold tracking-tight text-content-primary">
                Validation, Traceability &amp; Run History
              </h2>
              <p className="mt-1 text-sm text-content-muted">
                Evidence for human review and research evaluation
              </p>
            </div>
            <div className="flex items-center gap-3 pt-1">
              <span className="inline-flex items-center rounded-control border border-default bg-elevated px-3 py-1 text-xs font-semibold text-content-secondary">
                {effectiveRuns.length > 0
                  ? `${effectiveRuns.length} historical run${effectiveRuns.length === 1 ? '' : 's'}`
                  : 'No runs recorded'}
              </span>
            </div>
          </div>

          {/* Evidence status card */}
          <div className="rounded-panel border border-default bg-surface p-5 space-y-3">
            <div className="space-y-1">
              <h3 className="font-semibold text-content-primary text-base">
                {effectiveRuns.length > 0
                  ? 'Historical validation evidence available'
                  : 'Validation and traceability awaiting execution'}
              </h3>
              <p className="text-xs text-content-muted">
                {effectiveRuns.length > 0
                  ? 'Shared AgentRun lifecycle — inspect persisted runs'
                  : 'Deterministic validation runs alongside generation'}
              </p>
            </div>

            <p className="text-xs text-content-secondary">
              {effectiveRuns.length > 0
                ? 'No active run in the current session. Select a historical run below to inspect its persisted validation findings and traceability evidence without regenerating outputs.'
                : 'No validation findings or traceability evidence recorded yet. Complete Node 4 Human Review and execute Node 5 to generate design artifacts, validation findings, and traceability evidence.'}
            </p>

            {effectiveRuns.length === 0 && onNavigate && (
              <div className="pt-2">
                <Button
                  variant="primary"
                  size="small"
                  onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)}
                >
                  Go to Node 5 — Generate Design &amp; Planning
                </Button>
              </div>
            )}
          </div>

          {/* Historical Agent 2 runs table */}
          {effectiveRuns.length > 0 && (
            <div className="rounded-panel border border-default bg-surface p-5 space-y-4">
              <div>
                <h3 className="font-semibold text-content-primary text-base">Historical Agent 2 runs</h3>
                <p className="mt-0.5 text-xs text-content-muted">
                  Shared AgentRun lifecycle — reopen persisted results without regeneration.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm" aria-label="Historical Agent 2 runs table">
                  <thead>
                    <tr className="border-b border-default text-xs text-content-muted font-medium">
                      <th scope="col" className="pb-3 pr-4 font-medium">Run</th>
                      <th scope="col" className="pb-3 pr-4 font-medium">Created</th>
                      <th scope="col" className="pb-3 pr-4 font-medium">Status</th>
                      <th scope="col" className="pb-3 pr-4 font-medium">Outputs</th>
                      <th scope="col" className="pb-3 font-medium text-right sm:text-left">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-default">
                    {effectiveRuns.map((r) => {
                      const isRunFailed = r.status === 'FAILED'
                      const outputsArray = Array.isArray(r.selected_outputs)
                        ? r.selected_outputs
                        : r.output_manifest && typeof r.output_manifest === 'object'
                          ? Object.keys(r.output_manifest)
                          : []

                      let outputText = `${outputsArray.length} outputs`
                      if (isRunFailed) {
                        outputText =
                          (Array.isArray(r.errors) && r.errors[0]?.message) ||
                          (Array.isArray(r.errors) && typeof r.errors[0] === 'string' && r.errors[0]) ||
                          'Structured output invalid'
                      }

                      return (
                        <tr key={r.run_id} className="hover:bg-elevated/60 transition-colors">
                          <td className="py-3 pr-4 font-mono text-xs font-semibold text-content-primary">
                            {r.run_id}
                          </td>
                          <td className="py-3 pr-4 text-xs text-content-secondary whitespace-nowrap">
                            {formatRunDate(r.created_at || r.started_at)}
                          </td>
                          <td className="py-3 pr-4 text-xs font-semibold uppercase">
                            {isRunFailed ? (
                              <span className="text-state-danger">FAILED</span>
                            ) : (
                              <span className="text-state-success">COMPLETED</span>
                            )}
                          </td>
                          <td className="py-3 pr-4 text-xs text-content-secondary">
                            {outputText}
                          </td>
                          <td className="py-3 text-right sm:text-left">
                            <Button
                              variant="ghost"
                              size="small"
                              onClick={() => handleOpenHistoricalRun(r.run_id)}
                              aria-label={`Open run ${r.run_id}`}
                            >
                              Open
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Standalone scope disclaimer banner */}
          <div className="rounded-panel border border-default bg-surface p-4 text-xs text-content-muted">
            Standalone scope: no Agent 1/3/4 execution · no Orchestrator · no H2 · no integrated SKB write · no Jira Cloud sync · no RAG.
          </div>
        </div>
      )}

      {/* Navigation footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        {onNavigate ? (
          <Button
            variant="outline"
            size="small"
            onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING)}
          >
            ← Back to Node 5 (Generate)
          </Button>
        ) : <span />}
        {onNavigate && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="small"
              onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)}
            >
              Go to Node 7 (Planning Results) →
            </Button>
            <Button
              variant="ghost"
              size="small"
              onClick={() => onNavigate(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)}
            >
              Node 4 (Human Review)
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
