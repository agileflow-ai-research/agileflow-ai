import { useLocation } from 'react-router-dom'

import RoutePlaceholder from '../components/feedback/RoutePlaceholder.jsx'
import AuthLayout from '../layouts/AuthLayout.jsx'

function LoginPage() {
  const location = useLocation()
  const successMessage = location.state?.registrationSuccess

  return (
    <AuthLayout>
      <div className="w-full max-w-lg">
        {successMessage ? (
          <div
            className="mb-4 rounded-control border border-state-success/40 bg-state-success/10 px-4 py-3 text-sm text-state-success"
            role="status"
          >
            {successMessage}
          </div>
        ) : null}
        <RoutePlaceholder
          eyebrow="Public access"
          title="Login"
          description="The login experience will be implemented in Frontend Phase F1.5."
        />
      </div>
    </AuthLayout>
  )
}

export default LoginPage
