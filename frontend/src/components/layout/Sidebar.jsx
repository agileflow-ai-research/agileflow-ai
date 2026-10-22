import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { getProjects } from '../../services/projectService.js'
import Button from '../ui/Button.jsx'
import Brand from './Brand.jsx'
import NavigationIcon from './sidebar/NavigationIcon.jsx'
import ProjectNavigation from './sidebar/ProjectNavigation.jsx'
import StandaloneAgentNavigation from './sidebar/StandaloneAgentNavigation.jsx'

function userInitials(name) {
  if (typeof name !== 'string' || !name.trim()) return 'AF'
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
}

function SidebarContent({ projectsState, agentProjectsState, onNavigate, user, onLogout }) {
  const { pathname } = useLocation()
  return (
    <>
      <nav className="scrollbar-hidden mt-5 min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain pr-1" aria-label="Primary navigation">
        <ProjectNavigation projects={projectsState.data} loadStatus={projectsState.status} pathname={pathname} onNavigate={onNavigate} />
        <StandaloneAgentNavigation projects={agentProjectsState.data} loadStatus={agentProjectsState.status} pathname={pathname} onNavigate={onNavigate} />
      </nav>
      <div className="mt-4 border-t border-default/80 pt-4">
        <div className="flex min-w-0 items-center gap-3 px-1">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-accent-border/40 bg-brand-soft text-xs font-bold text-highlight" aria-hidden="true">{userInitials(user?.name)}</span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-content-primary">{user?.name}</p>
            <p className="truncate text-helper-copy text-content-muted">{user?.email}</p>
          </div>
        </div>
        <Button className="mt-3 w-full justify-start" variant="ghost" size="small" onClick={onLogout}>
          <NavigationIcon name="logout" />
          Log out
        </Button>
      </div>
    </>
  )
}

function Sidebar({ isOpen, isCollapsed, onClose, onNavigate, onToggleCollapse, agentProjectsState, user, onLogout }) {
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
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-default/80 bg-sidebar transition-[width,padding] duration-200 lg:flex ${isCollapsed ? 'w-[4.75rem] p-3' : 'w-72 p-4'}`} aria-label="Application sidebar">
        {isCollapsed ? (
          <div className="flex h-full flex-col items-center gap-3">
            <Brand mode="mark" size="small" className="mb-2 rounded-control p-1" />
            <button type="button" className="flex h-9 w-9 items-center justify-center rounded-control text-content-muted transition-colors hover:bg-elevated hover:text-content-primary" aria-label="Expand sidebar" aria-expanded="false" onClick={onToggleCollapse}>
              <NavigationIcon name="collapse" className="rotate-180" />
            </button>
            <div className="my-1 h-px w-8 bg-default/80" />
            <span className="flex h-9 w-9 items-center justify-center rounded-control text-content-muted" title="Projects"><NavigationIcon name="projects" /></span>
            <span className="flex h-9 w-9 items-center justify-center rounded-control text-content-muted" title="Standalone Agents"><NavigationIcon name="agents" /></span>
            <button type="button" className="mt-auto flex h-9 w-9 items-center justify-center rounded-control text-content-muted transition-colors hover:bg-elevated hover:text-content-primary" aria-label="Log out" onClick={onLogout}><NavigationIcon name="logout" /></button>
          </div>
        ) : (
          <>
            <div className="flex h-11 items-center justify-between gap-3 border-b border-default/70 pb-3">
              <Brand size="small" />
              <button type="button" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-content-muted transition-colors hover:bg-elevated hover:text-content-primary" aria-label="Collapse sidebar" aria-expanded="true" onClick={onToggleCollapse}><NavigationIcon name="collapse" /></button>
            </div>
            <SidebarContent {...contentProps} />
          </>
        )}
      </aside>

      {isOpen ? (
        <>
          <button type="button" className="fixed inset-0 z-30 bg-canvas/80 backdrop-blur-sm lg:hidden" aria-label="Close navigation" onClick={onClose} />
          <aside className="fixed inset-y-0 left-0 z-40 flex w-[min(20rem,90vw)] flex-col border-r border-default bg-sidebar p-4 shadow-surface lg:hidden" aria-label="Mobile navigation">
            <div className="flex h-11 items-center justify-between gap-4 border-b border-default/70 pb-3">
              <Brand size="small" />
              <button type="button" className="flex h-9 w-9 items-center justify-center rounded-control text-content-secondary hover:bg-elevated" aria-label="Close navigation" onClick={onClose}><NavigationIcon name="close" /></button>
            </div>
            <SidebarContent {...contentProps} onNavigate={onNavigate} />
          </aside>
        </>
      ) : null}
    </>
  )
}

export default Sidebar
