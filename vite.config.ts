/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Keep the third-party code the app always needs in stable, separately cached
 * chunks: a change to our own source no longer invalidates React or Supabase
 * in the browser cache, and no single chunk trips Vite's 500 kB warning.
 */
function vendorChunk(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  if (/node_modules\/(framer-motion|motion-dom|motion-utils)\//.test(id)) return 'motion'
  if (id.includes('node_modules/@dnd-kit/')) return 'dnd-kit'
  if (id.includes('node_modules/@supabase/')) return 'supabase'
  if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'react'
  return undefined
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { manualChunks: vendorChunk },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
