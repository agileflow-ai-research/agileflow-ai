import { useState } from 'react'

import Input from './Input.jsx'

function PasswordInput({ disabled = false, ...inputProps }) {
  const [isVisible, setIsVisible] = useState(false)
  const toggleLabel = isVisible ? 'Hide password' : 'Show password'

  return (
    <Input
      {...inputProps}
      type={isVisible ? 'text' : 'password'}
      disabled={disabled}
      trailingContent={
        <button
          type="button"
          disabled={disabled}
          aria-label={toggleLabel}
          className="rounded-control px-2 py-1 text-helper-copy font-semibold text-content-secondary transition-colors hover:text-content-primary disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => setIsVisible((current) => !current)}
        >
          {isVisible ? 'Hide' : 'Show'}
        </button>
      }
    />
  )
}

export default PasswordInput
