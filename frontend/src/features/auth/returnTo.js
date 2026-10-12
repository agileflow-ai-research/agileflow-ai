export function getSafeReturnPath(from) {
  const pathname = from?.pathname
  const isProjectPath =
    pathname === '/projects' ||
    pathname === '/projects/new' ||
    /^\/projects\/PRJ-\d+$/.test(pathname ?? '')

  if (!isProjectPath) {
    return '/projects'
  }

  const search = typeof from.search === 'string' ? from.search : ''
  const hash = typeof from.hash === 'string' ? from.hash : ''
  return `${pathname}${search}${hash}`
}
