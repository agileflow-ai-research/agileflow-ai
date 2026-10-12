function FormError({ children }) {
  if (!children) {
    return null
  }

  return (
    <div className="rounded-control border border-state-danger/40 bg-state-danger/10 px-3 py-2 text-sm text-state-danger" role="alert">
      {children}
    </div>
  )
}

export default FormError
