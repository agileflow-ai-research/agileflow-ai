import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { getProjects } from '../../services/projectService.js'
import Button from '../ui/Button.jsx'
import Brand from './Brand.jsx'
import ProjectNavigation from './sidebar/ProjectNavigation.jsx'
import StandaloneAgentNavigation from './sidebar/StandaloneAgentNavigation.jsx'

function userInitials(name) {
  if (typeof name !== 'string' || !name.trim()) return 'AF'
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
}

function SidebarContent({ projectsState, agentProjectsState, onNavigate, user, onLogout, showBrand = true }) {
  const { pathname } = useLocation()
  return (
    <>
      {showBrand ? <Brand /> : null}
      <nav className="mt-8 min-h-0 flex-1 space-y-7 overflow-y-auto pr-1" aria-label="Primary navigation">
        <ProjectNavigation projects={projectsState.data} loadStatus={projectsState.status} pathname={pathname} onNavigate={onNavigate} />
        <StandaloneAgentNavigation projects={agentProjectsState.data} loadStatus={agentProjectsState.status} pathname={pathname} onNavigate={onNavigate} />
      </nav>
      <div className="mt-5 border-t border-default pt-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-bold text-content-primary" aria-hidden="true">{userInitials(user?.name)}</span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-content-primary">{user?.name}</p>
            <p className="truncate text-helper-copy text-content-muted">{user?.email}</p>
          </div>
        </div>
        <Button className="mt-4 w-full" variant="ghost" size="small" onClick={onLogout}>Log out</Button>
      </div>
    </>
  )
}

function Sidebar({
  isOpen,
  isCollapsed,
  onClose,
  onNavigate,
  onToggleCollapse,
  agentProjectsState,
  user,
  onLogout,
}) {
  const [projectsState, setProjectsState] = useState({ status: 'loading', data: [] })

  useEffect(() => {
    let active = true
    getProjects().then((projectsResult) => {
      if (!active) return
      setProjectsState(
        Array.isArray(projectsResult?.data)
          ? { status: 'success', data: projectsResult.data }
          : { status: 'error', data: [] },
      )
    }).catch(() => {
      if (active) setProjectsState({ status: 'error', data: [] })
    })
    return () => { active = false }
  }, [])

  const contentProps = { projectsState, agentProjectsState, user, onLogout }
  return (
    <>
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-default bg-sidebar transition-[width] lg:flex ${isCollapsed ? 'w-20 p-3' : 'w-80 p-5'}`} aria-label="Application sidebar">
        <button
          type="button"
          className="mb-3 min-h-9 rounded-control border border-default text-xs font-semibold text-content-secondary hover:bg-elevated hover:text-content-primary"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!isCollapsed}
          onClick={onToggleCollapse}
        >
          {isCollapsed ? '›' : 'Collapse'}
        </button>
        {isCollapsed ? (
          <div className="flex flex-1 flex-col items-center gap-5 pt-2">
            <Brand mode="mark" size="small" />
            <span className="text-center text-xs font-semibold text-content-muted">Projects</span>
            <span className="text-center text-xs font-semibold text-content-muted">Agents</span>
          </div>
        ) : <SidebarContent {...contentProps} />}
      </aside>

      {isOpen ? (
        <>
          <button type="button" className="fixed inset-0 z-30 bg-canvas/80 lg:hidden" aria-label="Close navigation" onClick={onClose} />
          <aside className="fixed inset-y-0 left-0 z-40 flex w-80 flex-col border-r border-default bg-sidebar p-5 lg:hidden" aria-label="Mobile navigation">
            <div className="flex items-center justify-between gap-4">
              <Brand />
              <button type="button" className="rounded-control px-2 py-1 text-content-secondary hover:bg-elevated" aria-label="Close navigation" onClick={onClose}>Close</button>
            </div>
            <SidebarContent {...contentProps} onNavigate={onNavigate} showBrand={false} />
          </aside>
        </>
      ) : null}
    </>
  )
}

export default Sidebar
