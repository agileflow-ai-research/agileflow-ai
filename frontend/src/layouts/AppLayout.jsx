import { useCallback, useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'

import Brand from '../components/layout/Brand.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import NavigationIcon from '../components/layout/sidebar/NavigationIcon.jsx'
import { useAuth } from '../features/auth/useAuth.js'
import { getAgentProjects } from '../services/agentProjectService.js'

function AppLayout() {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [agentProjectsState, setAgentProjectsState] = useState({ status: 'loading', data: [] })
  const navigationTriggerRef = useRef(null)
  const agentProjectsRequestSequence = useRef(0)
  const { user, logout } = useAuth()

  const refreshAgentProjects = useCallback(async () => {
    const requestId = agentProjectsRequestSequence.current + 1
    agentProjectsRequestSequence.current = requestId
    try {
      const response = await getAgentProjects()
      if (requestId !== agentProjectsRequestSequence.current) return null
      if (!Array.isArray(response?.data)) throw new Error('Invalid agent projects response')
      setAgentProjectsState({ status: 'success', data: response.data })
      return response.data
    } catch (error) {
      if (requestId !== agentProjectsRequestSequence.current) return null
      if (error?.status === 401) return null
      setAgentProjectsState((current) => (
        current.data.length > 0 ? current : { status: 'error', data: [] }
      ))
      return null
    }
  }, [])

  useEffect(() => {
    const loadTimer = window.setTimeout(() => { void refreshAgentProjects() }, 0)
    return () => {
      window.clearTimeout(loadTimer)
      agentProjectsRequestSequence.current += 1
    }
  }, [refreshAgentProjects])

  const closeNavigation = useCallback((restoreFocus = false) => {
    setIsNavigationOpen(false)
    if (restoreFocus) navigationTriggerRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!isNavigationOpen) return undefined

    function handleKeyDown(event) {
      if (event.key === 'Escape') closeNavigation(true)
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [closeNavigation, isNavigationOpen])

  return (
    <div className="min-h-screen bg-canvas text-content-primary lg:flex">
      <Sidebar
        isOpen={isNavigationOpen}
        isCollapsed={isSidebarCollapsed}
        onClose={() => closeNavigation(true)}
        onNavigate={() => closeNavigation(false)}
        onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
        agentProjectsState={agentProjectsState}
        user={user}
        onLogout={logout}
      />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-default/80 bg-sidebar/95 px-page backdrop-blur lg:hidden">
          <Brand mode="wordmark" size="small" />
          <button
            ref={navigationTriggerRef}
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-button border border-default bg-elevated text-content-primary"
            aria-label="Open navigation"
            aria-expanded={isNavigationOpen}
            onClick={() => setIsNavigationOpen(true)}
          >
            <NavigationIcon name="menu" />
          </button>
        </header>
        <Outlet context={{ refreshAgentProjects }} />
      </div>
    </div>
  )
}

export default AppLayout
