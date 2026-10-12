import { Outlet } from 'react-router-dom'

import Brand from '../components/layout/Brand.jsx'

function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-content-primary">
      <header className="border-b border-default bg-sidebar">
        <div className="mx-auto flex w-full max-w-content items-center px-page py-4">
          <Brand />
        </div>
      </header>
      <Outlet />
    </div>
  )
}

export default AppLayout
