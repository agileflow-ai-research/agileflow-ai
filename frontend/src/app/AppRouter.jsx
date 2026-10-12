import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AuthProvider from '../features/auth/AuthProvider.jsx'
import ProtectedRoute from '../features/auth/ProtectedRoute.jsx'
import PublicOnlyRoute from '../features/auth/PublicOnlyRoute.jsx'
import AppLayout from '../layouts/AppLayout.jsx'
import CreateProjectPage from '../pages/CreateProjectPage.jsx'
import LoginPage from '../pages/LoginPage.jsx'
import ProjectOverviewPage from '../pages/ProjectOverviewPage.jsx'
import ProjectsPage from '../pages/ProjectsPage.jsx'
import RegisterPage from '../pages/RegisterPage.jsx'

function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/new" element={<CreateProjectPage />} />
              <Route path="/projects/:projectId" element={<ProjectOverviewPage />} />
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default AppRouter
