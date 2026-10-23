import AuthIllustration from '../components/auth/AuthIllustration.jsx'
import Brand from '../components/layout/Brand.jsx'
import ThemeToggle from '../components/layout/ThemeToggle.jsx'
import { cn } from '../utils/cn.js'

function AuthLayout({ illustrationSrc, illustrationAlt = '', children }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-content-primary lg:flex-row">
      {/* ── Left branded panel ── */}
      {illustrationSrc && (
        <aside className="auth-panel-left relative hidden overflow-hidden lg:flex lg:w-[52%] xl:w-[54%]">
          {/* Background gradient */}
          <div className="absolute inset-0 auth-gradient" />

          {/* Decorative floating orbs */}
          <div className="auth-orb auth-orb--1" />
          <div className="auth-orb auth-orb--2" />
          <div className="auth-orb auth-orb--3" />

          {/* Grid pattern overlay */}
          <div className="absolute inset-0 auth-grid-pattern opacity-[0.03]" />

          {/* Content */}
          <div className="relative z-10 flex h-full w-full flex-col justify-between px-10 py-8 xl:px-14">
            {/* Top: Brand */}
            <div className="flex items-center">
              <Brand mode="full" size="medium" />
            </div>

            {/* Center: Illustration + tagline */}
            <div className="flex flex-1 flex-col items-center justify-center gap-6 py-4">
              <AuthIllustration className="w-full max-w-sm drop-shadow-2xl xl:max-w-md" />
              <div className="text-center">
                <h2 className="text-2xl font-bold tracking-tight text-white xl:text-3xl">
                  AI-Powered Project Management
                </h2>
                <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-white/70 xl:text-base">
                  Streamline your agile workflow with intelligent agents that plan, design, and deliver.
                </p>
              </div>

            </div>

            {/* Bottom: testimonial */}
            <div className="auth-testimonial">
              <p className="text-sm leading-relaxed text-white/80 italic">
                &ldquo;AgileFlow AI has transformed how our team approaches project planning.
                What used to take days now takes minutes.&rdquo;
              </p>
              <p className="mt-3 text-xs font-semibold text-white/50">
                — Trusted by agile teams worldwide
              </p>
            </div>
          </div>
        </aside>
      )}

      {/* ── Right form panel ── */}
      <div
        className={cn(
          'flex min-h-screen flex-1 flex-col bg-canvas',
          illustrationSrc && 'lg:min-h-0',
        )}
      >
        {/* Mobile header */}
        <header className="flex items-center justify-between px-6 py-5 sm:px-8 lg:justify-end">
          <div className="lg:hidden">
            <Brand mode="full" size="medium" />
          </div>
          <ThemeToggle compact />
        </header>

        {/* Form area */}
        <div className="flex flex-1 items-center justify-center px-6 pb-12 sm:px-8">
          <div className="w-full max-w-[28rem]">{children}</div>
        </div>
      </div>
    </div>
  )
}

export default AuthLayout
