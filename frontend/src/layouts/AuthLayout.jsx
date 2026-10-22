import Brand from '../components/layout/Brand.jsx'
import ThemeToggle from '../components/layout/ThemeToggle.jsx'
import { cn } from '../utils/cn.js'

function AuthLayout({ illustrationSrc, illustrationAlt = '', children }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-content-primary">
      <header className="mx-auto flex w-full max-w-content items-center justify-between px-page py-6">
        <Brand mode="wordmark" />
        <ThemeToggle compact />
      </header>
      <div
        className={cn(
          'mx-auto grid w-full max-w-content flex-1 items-center gap-8 px-page pb-10 lg:gap-12',
          illustrationSrc && 'lg:grid-cols-2',
        )}
      >
        {illustrationSrc ? (
          <aside className="hidden h-full min-h-0 items-center justify-center lg:flex">
            <img
              data-testid="auth-illustration"
              className="max-h-[72vh] w-full object-contain"
              src={illustrationSrc}
              alt={illustrationAlt}
            />
          </aside>
        ) : null}

        <div
          className={cn(
            'flex w-full justify-center',
            !illustrationSrc && 'lg:col-span-2',
          )}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

export default AuthLayout
