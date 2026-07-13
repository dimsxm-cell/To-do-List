import { createClient } from '@supabase/supabase-js'

export function validateSupabaseConfig(url?: string, key?: string): { url: string; key: string } {
  if (!url || !key) {
    throw new Error(
      'Missing Supabase config: set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env'
    )
  }
  return { url, key }
}

const { url, key } = validateSupabaseConfig(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

export const supabase = createClient(url, key)
