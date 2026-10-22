import { cn } from '../../utils/cn.js'
import { useTheme } from '../../features/theme/useTheme.js'

function ThemeGlyph({ theme }) {
  return theme === 'dark' ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
      <path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z" />
    </svg>
  )
}

function ThemeToggle({ compact = false, className }) {
  const { theme, toggleTheme } = useTheme()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  const label = `Switch to ${nextTheme} theme`

  return (
    <button
      type="button"
      className={cn(
        'flex min-h-9 items-center rounded-control text-sm font-semibold text-content-secondary transition-colors hover:bg-elevated hover:text-content-primary',
        compact ? 'h-9 w-9 justify-center' : 'w-full gap-2 px-3 py-1.5',
        className,
      )}
      aria-label={label}
      title={label}
      onClick={toggleTheme}
    >
      <ThemeGlyph theme={theme} />
      {compact ? null : <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>}
    </button>
  )
}

export default ThemeToggle
