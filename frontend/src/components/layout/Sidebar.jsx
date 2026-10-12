import { Link, useLocation } from 'react-router-dom'

import { cn } from '../../utils/cn.js'
import Button from '../ui/Button.jsx'
import Brand from './Brand.jsx'

function userInitials(name) {
  if (typeof name !== 'string' || !name.trim()) return 'AF'

  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

function Sidebar({ isOpen, onClose, user, onLogout }) {
  const location = useLocation()
  const projectsActive =
    location.pathname === '/projects' || location.pathname.startsWith('/projects/')

  return (
    <>
      {isOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-canvas/80 lg:hidden"
          aria-label="Close navigation"
          onClick={onClose}
        />
      ) : null}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-default bg-sidebar p-6 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Application sidebar"
      >
        <div className="flex items-center justify-between gap-4">
          <Brand />
          <button
            type="button"
            className="rounded-control px-2 py-1 text-content-secondary hover:bg-elevated hover:text-content-primary lg:hidden"
            aria-label="Close navigation"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <nav className="mt-10" aria-label="Primary navigation">
          <p className="mb-3 text-helper-copy font-semibold uppercase tracking-wider text-content-muted">
            Workspace
          </p>
          <Link
            to="/projects"
            onClick={onClose}
            aria-current={projectsActive ? 'page' : undefined}
            className={cn(
              'flex min-h-11 items-center rounded-button px-4 py-2.5 text-sm font-semibold transition-colors',
              projectsActive
                ? 'bg-brand-soft text-content-primary'
                : 'text-content-secondary hover:bg-elevated hover:text-content-primary',
            )}
          >
            Projects
          </Link>
        </nav>

        <div className="mt-auto border-t border-default pt-5">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-bold text-content-primary"
              aria-hidden="true"
            >
              {userInitials(user?.name)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-content-primary">
                {user?.name}
              </p>
              <p className="truncate text-helper-copy text-content-muted">
                {user?.email}
              </p>
            </div>
          </div>
          <Button
            className="mt-4 w-full"
            variant="ghost"
            size="small"
            onClick={onLogout}
          >
            Log out
          </Button>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
