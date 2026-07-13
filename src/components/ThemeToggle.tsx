import { useEffect, useState } from 'react'
import { strings } from '../copy/strings'

function getInitialTheme(): 'light' | 'dark' {
  const stored = window.localStorage.getItem('theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    window.localStorage.setItem('theme', theme)
  }, [theme])

  return (
    <button
      onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
      aria-label={strings.common.themeToggle}
      className="fixed right-4 top-4 rounded-full bg-white p-2 text-lg shadow dark:bg-slate-800"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
