import { Outlet } from 'react-router-dom'

import Brand from '../components/layout/Brand.jsx'

function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-content-primary">
      <header className="mx-auto flex w-full max-w-content px-page py-6">
        <Brand />
      </header>
      <Outlet />
    </div>
  )
}

export default AuthLayout
