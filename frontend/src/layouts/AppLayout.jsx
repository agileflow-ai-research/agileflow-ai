import { useState } from 'react'
import { Outlet } from 'react-router-dom'

import Brand from '../components/layout/Brand.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import { useAuth } from '../features/auth/useAuth.js'

function AppLayout() {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-canvas text-content-primary lg:flex">
      <Sidebar
        isOpen={isNavigationOpen}
        onClose={() => setIsNavigationOpen(false)}
        user={user}
        onLogout={logout}
      />
      <div className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-default bg-sidebar px-page py-4 lg:hidden">
          <Brand mode="wordmark" size="small" />
          <button
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
