import { useCallback, useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'

import Brand from '../components/layout/Brand.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import { useAuth } from '../features/auth/useAuth.js'

function AppLayout() {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const navigationTriggerRef = useRef(null)
  const { user, logout } = useAuth()

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
        user={user}
        onLogout={logout}
      />
      <div className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-default bg-sidebar px-page py-4 lg:hidden">
          <Brand mode="wordmark" size="small" />
          <button
            ref={navigationTriggerRef}
            type="button"
            className="rounded-button border border-default bg-elevated px-3 py-2 text-sm font-semibold text-content-primary"
            aria-label="Open navigation"
            aria-expanded={isNavigationOpen}
            onClick={() => setIsNavigationOpen(true)}
          >
            Menu
          </button>
        </header>
        <Outlet />
      </div>
    </div>
  )
}

export default AppLayout
