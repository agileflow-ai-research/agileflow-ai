import { Link } from 'react-router-dom'

import { cn } from '../../../utils/cn.js'
import NavigationIcon from './NavigationIcon.jsx'

function SidebarProjectItem({ label, status, to, selected, onNavigate }) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-current={selected ? 'page' : undefined}
      className={cn(
        'group relative flex min-h-8 items-center gap-2 rounded-control px-2 py-1.5 text-[0.8125rem] transition-colors',
        selected
          ? 'bg-brand-soft font-semibold text-content-primary ring-1 ring-inset ring-accent-border/25'
          : 'text-content-secondary hover:bg-elevated hover:text-content-primary',
      )}
    >
      <span className="relative shrink-0 text-content-muted" aria-hidden="true">
        <NavigationIcon name="project" className="h-3.5 w-3.5" />
        <span className={cn('absolute -bottom-0.5 -right-0.5 h-1.5 w-1.5 rounded-full ring-2 ring-sidebar', status === 'ARCHIVED' ? 'bg-content-muted' : 'bg-state-success')} />
      </span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {status ? <span className="sr-only">{status === 'ARCHIVED' ? 'Archived' : 'Active'}</span> : null}
    </Link>
  )
}

export default SidebarProjectItem
