import { createContext } from 'react'

export const THEME_STORAGE_KEY = 'agileflow_theme'

export const ThemeContext = createContext({
  theme: 'dark',
  setTheme: () => {},
  toggleTheme: () => {},
})
