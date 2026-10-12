import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import signupIllustration from '../assets/auth/signup-illustration.png'
import FormError from '../components/feedback/FormError.jsx'
import Button from '../components/ui/Button.jsx'
import Input from '../components/ui/Input.jsx'
import PasswordInput from '../components/ui/PasswordInput.jsx'
import AuthLayout from '../layouts/AuthLayout.jsx'
import { register } from '../services/authService.js'

const initialForm = { name: '', email: '', password: '' }
const genericRegistrationError =
  "We couldn't create your account right now. Please try again."

function validateForm({ name, email, password }) {
  const errors = {}

  if (!name.trim()) errors.name = 'Enter your full name.'
  if (!email.trim()) {
    errors.email = 'Enter your work email.'
  } else if (!/^[^\s@]+@[^\s@]+$/.test(email.trim())) {
    errors.email = 'Enter a valid email address.'
  }
  if (!password) errors.password = 'Enter a password.'

  return errors
}

function mapFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}

  return errors.reduce((mappedErrors, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['name', 'email', 'password'].includes(field) && error?.message) {
      mappedErrors[field] = error.message
    }
    return mappedErrors
  }, {})
}

function RegisterPage() {
  const navigate = useNavigate()
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
    try {
      await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      navigate('/login', {
        replace: true,
        state: {
          registrationSuccess:
            'Account created successfully. Sign in to continue.',
        },
      })
    } catch (error) {
      const backendFieldErrors = mapFieldErrors(error?.errors)
      if (Object.keys(backendFieldErrors).length > 0) {
        setFieldErrors((current) => ({ ...current, ...backendFieldErrors }))
      } else if (error?.status === 409) {
        setSubmissionError(
          'An account with this email already exists. Try signing in instead.',
        )
      } else {
        setSubmissionError(genericRegistrationError)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout illustrationSrc={signupIllustration} illustrationAlt="">
      <main className="w-full max-w-lg rounded-panel border border-default bg-surface p-6 shadow-card sm:p-8 lg:p-10">
        <div className="mb-8">
          <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-brand-primary">
            Get started
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-content-primary sm:text-4xl">
            Create your account
          </h1>
          <p className="mt-3 text-content-secondary">
            Start your AgileFlow AI journey today.
          </p>
        </div>

        <form className="space-y-5" noValidate onSubmit={handleSubmit}>
          <Input
            label="Full name"
            name="name"
            placeholder="John Doe"
            value={form.name}
            onChange={handleChange}
            autoComplete="name"
            required
            disabled={isSubmitting}
            error={fieldErrors.name}
          />
          <Input
            label="Work email"
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
            placeholder="Create a password"
            value={form.password}
            onChange={handleChange}
            autoComplete="new-password"
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
            loadingLabel="Creating account"
          >
            Create account
          </Button>
        </form>

        <p className="mt-7 text-center text-sm text-content-secondary">
          Already have an account?{' '}
          <Link
            className="font-semibold text-brand-primary transition-colors hover:text-brand-hover"
            to="/login"
          >
            Sign in
          </Link>
        </p>
      </main>
    </AuthLayout>
  )
}

export default RegisterPage
