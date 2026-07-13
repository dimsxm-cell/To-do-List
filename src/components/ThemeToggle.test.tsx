import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeToggle } from './ThemeToggle'
import { strings } from '../copy/strings'

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addListener: () => {},
      removeListener: () => {},
    }),
  })
})

describe('ThemeToggle', () => {
  it('starts in light mode by default', () => {
    render(<ThemeToggle />)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('toggles to dark mode and persists it', () => {
    render(<ThemeToggle />)
    fireEvent.click(screen.getByLabelText(strings.common.themeToggle))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(window.localStorage.getItem('theme')).toBe('dark')
  })
})
