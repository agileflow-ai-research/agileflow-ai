import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import loginIllustration from '../assets/auth/login-illustration.png'
import FormError from '../components/feedback/FormError.jsx'
import Button from '../components/ui/Button.jsx'
import Input from '../components/ui/Input.jsx'
import PasswordInput from '../components/ui/PasswordInput.jsx'
import { getSafeReturnPath } from '../features/auth/returnTo.js'
import { useAuth } from '../features/auth/useAuth.js'
import AuthLayout from '../layouts/AuthLayout.jsx'
import { login } from '../services/authService.js'

const initialForm = { email: '', password: '' }
const genericLoginError = "We couldn't sign you in right now. Please try again."

function validateForm({ email, password }) {
  const errors = {}

  if (!email.trim()) {
    errors.email = 'Enter your email.'
  } else if (!/^[^\s@]+@[^\s@]+$/.test(email.trim())) {
    errors.email = 'Enter a valid email address.'
  }
  if (!password) errors.password = 'Enter your password.'

  return errors
}

function mapFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}

  return errors.reduce((mappedErrors, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['email', 'password'].includes(field) && error?.message) {
      mappedErrors[field] = error.message
    }
    return mappedErrors
  }, {})
}

function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { establishSession } = useAuth()
  const successMessage = location.state?.registrationSuccess
  const returnPath = getSafeReturnPath(location.state?.from)
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submissionError, setSubmissionError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleChange(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const nextErrors = { ...current }
      delete nextErrors[name]
      return nextErrors
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (isSubmitting) return

    setSubmissionError('')
    const validationErrors = validateForm(form)
    setFieldErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    setIsSubmitting(true)
    let response
    try {
      response = await login({
        email: form.email.trim(),
        password: form.password,
      })
    } catch (error) {
      if (error?.status === 401) {
        setSubmissionError('Invalid email or password.')
      } else {
        const backendFieldErrors = mapFieldErrors(error?.errors)
        if (Object.keys(backendFieldErrors).length > 0) {
          setFieldErrors((current) => ({ ...current, ...backendFieldErrors }))
        } else {
          setSubmissionError(genericLoginError)
        }
      }
      setIsSubmitting(false)
      return
    }

    const accessToken = response?.data?.access_token
    if (typeof accessToken !== 'string' || !accessToken.trim()) {
      setSubmissionError(genericLoginError)
      setIsSubmitting(false)
      return
    }

    try {
      await establishSession(accessToken)
      navigate(returnPath, { replace: true })
    } catch {
      setSubmissionError(genericLoginError)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout illustrationSrc={loginIllustration} illustrationAlt="">
      <main className="w-full max-w-lg rounded-panel border border-default bg-surface p-6 shadow-card sm:p-8 lg:p-10">
        {successMessage ? (
          <div
            className="mb-6 rounded-control border border-state-success/40 bg-state-success-soft px-4 py-3 text-sm text-state-success"
            role="status"
          >
            {successMessage}
          </div>
        ) : null}

        <div className="mb-8">
          <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-brand">
            Sign in
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-content-primary sm:text-4xl">
            Welcome back
          </h1>
          <p className="mt-3 text-content-secondary">
            Sign in to your AgileFlow AI account to continue.
          </p>
        </div>

        <form className="space-y-5" noValidate onSubmit={handleSubmit}>
          <Input
            label="Email"
            name="email"
            type="email"
            placeholder="you@company.com"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
            required
            disabled={isSubmitting}
            error={fieldErrors.email}
          />
          <PasswordInput
            label="Password"
            name="password"
            placeholder="Enter your password"
            value={form.password}
            onChange={handleChange}
            autoComplete="current-password"
            required
            disabled={isSubmitting}
            error={fieldErrors.password}
          />

          <FormError>{submissionError}</FormError>

          <Button
            className="w-full"
            type="submit"
            size="large"
            loading={isSubmitting}
            loadingLabel="Signing in"
          >
            Sign in
          </Button>
        </form>

        <p className="mt-7 text-center text-sm text-content-secondary">
          Don&apos;t have an account?{' '}
          <Link
            className="font-semibold text-brand transition-colors hover:text-brand-hover"
            to="/register"
            state={{ from: location.state?.from }}
          >
            Create account
          </Link>
        </p>
      </main>
    </AuthLayout>
  )
}

export default LoginPage
