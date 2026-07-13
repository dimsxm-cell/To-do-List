import { describe, it, expect } from 'vitest'
import { validateSupabaseConfig } from './supabase'

describe('validateSupabaseConfig', () => {
  it('returns url and key when both provided', () => {
    expect(validateSupabaseConfig('https://x.supabase.co', 'anon-key')).toEqual({
      url: 'https://x.supabase.co',
      key: 'anon-key',
    })
  })

  it('throws when url is missing', () => {
    expect(() => validateSupabaseConfig(undefined, 'anon-key')).toThrow(/Missing Supabase config/)
  })

  it('throws when key is missing', () => {
    expect(() => validateSupabaseConfig('https://x.supabase.co', undefined)).toThrow(/Missing Supabase config/)
  })
})
