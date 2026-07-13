import { describe, it, expect } from 'vitest'
import { strings } from './strings'

function collectValues(obj: unknown): string[] {
  if (typeof obj === 'string') return [obj]
  if (obj && typeof obj === 'object') return Object.values(obj).flatMap(collectValues)
  return []
}

describe('strings', () => {
  it('has no empty copy values', () => {
    const values = collectValues(strings)
    expect(values.length).toBeGreaterThan(0)
    expect(values.every((v) => v.trim().length > 0)).toBe(true)
  })

  it('exposes the keys components rely on', () => {
    expect(strings.auth.emailPlaceholder).toBeTruthy()
    expect(strings.tasks.addPlaceholder).toBeTruthy()
    expect(strings.toast.taskAdded).toBeTruthy()
    expect(strings.common.signOut).toBeTruthy()
  })
})
