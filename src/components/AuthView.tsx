import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { strings } from '../copy/strings'
import { useToast } from './Toast'
import type { useAuth } from '../hooks/useAuth'

type AuthHook = ReturnType<typeof useAuth>

export function AuthView({ auth }: { auth: AuthHook }) {
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { showToast } = useToast()

  const isSignIn = mode === 'signIn'
  const t = strings.auth

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    const success = isSignIn ? await auth.signIn(email, password) : await auth.signUp(email, password)
    setSubmitting(false)
    if (success) showToast(isSignIn ? strings.toast.signedIn : strings.toast.signedUp)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-900">
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-xl dark:bg-slate-800"
      >
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">
          {isSignIn ? t.titleSignIn : t.titleSignUp}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {isSignIn ? t.subtitleSignIn : t.subtitleSignUp}
        </p>

        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t.emailPlaceholder}
          className="mt-6 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />
        <input
          type="password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t.passwordPlaceholder}
          className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />

        {auth.error && (
          <p className="mt-3 text-sm text-rose-500" role="alert">
            {auth.error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-5 w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-60"
        >
          {submitting ? t.loading : isSignIn ? t.submitSignIn : t.submitSignUp}
        </button>

        <button
          type="button"
          onClick={() => setMode(isSignIn ? 'signUp' : 'signIn')}
          className="mt-4 w-full text-center text-sm text-indigo-600 hover:underline dark:text-indigo-400"
        >
          {isSignIn ? t.switchToSignUp : t.switchToSignIn}
        </button>
      </motion.form>
    </div>
  )
}
