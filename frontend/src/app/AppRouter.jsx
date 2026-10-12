import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout.jsx'
import CreateProjectPage from '../pages/CreateProjectPage.jsx'
import LoginPage from '../pages/LoginPage.jsx'
import ProjectOverviewPage from '../pages/ProjectOverviewPage.jsx'
import ProjectsPage from '../pages/ProjectsPage.jsx'
import RegisterPage from '../pages/RegisterPage.jsx'

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<AppLayout />}>
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/new" element={<CreateProjectPage />} />
          <Route path="/projects/:projectId" element={<ProjectOverviewPage />} />
        </Route>

        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter
