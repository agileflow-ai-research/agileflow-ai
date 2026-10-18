import { Link } from 'react-router-dom'

import { cn } from '../../../utils/cn.js'

function SidebarProjectItem({ label, status, to, selected, onNavigate }) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-current={selected ? 'page' : undefined}
      className={cn(
        'group flex min-h-9 items-center gap-2 rounded-control px-3 py-2 text-sm transition-colors',
        selected
          ? 'bg-brand-soft font-semibold text-content-primary'
          : 'text-content-secondary hover:bg-elevated hover:text-content-primary',
      )}
    >
      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', status === 'ARCHIVED' ? 'bg-content-muted' : 'bg-state-success')} aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {status ? <span className="sr-only">{status === 'ARCHIVED' ? 'Archived' : 'Active'}</span> : null}
    </Link>
  )
}

export default SidebarProjectItem
