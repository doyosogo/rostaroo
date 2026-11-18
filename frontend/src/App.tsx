import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import type { Organisation } from './api'
import {
  AuthForm,
  buttonClass,
  errorMessage,
  linkClass,
  OrganisationForm,
} from './Forms'

type Session =
  | { status: 'loading' | 'guest' }
  | { status: 'error'; message: string }
  | { status: 'authenticated'; organisation: Organisation | null }

export default function App() {
  const [session, setSession] = useState<Session>({ status: 'loading' })
  const [page, setPage] = useState<'welcome' | 'register' | 'login'>('welcome')
  const [attempt, setAttempt] = useState(0)
  const [signingOut, setSigningOut] = useState(false)
  const [logoutError, setLogoutError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function restoreSession() {
      try {
        await api.me(controller.signal)
        const organisations = await api.organisations(controller.signal)
        if (!controller.signal.aborted) {
          setSession({
            status: 'authenticated',
            organisation: organisations[0] ?? null,
          })
        }
      } catch (cause) {
        if (controller.signal.aborted) return
        if (cause instanceof ApiError && cause.status === 401) {
          setSession({ status: 'guest' })
        } else {
          setSession({ status: 'error', message: errorMessage(cause) })
        }
      }
    }

    void restoreSession()
    return () => controller.abort()
  }, [attempt])

  function refreshSession() {
    setSession({ status: 'loading' })
    setAttempt((current) => current + 1)
  }

  function returnToLogin() {
    setPage('login')
    setSession({ status: 'guest' })
  }

  async function logout() {
    setSigningOut(true)
    setLogoutError('')
    try {
      await api.logout()
      returnToLogin()
    } catch (cause) {
      setLogoutError(errorMessage(cause))
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-6xl flex-col px-6 sm:px-12">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#cbd8cc] py-7">
        <p className="text-2xl font-bold tracking-tight text-[#244c3e]">
          Rostaroo
          <span aria-hidden="true" className="text-[#537d64]">
            .
          </span>
        </p>
        {session.status === 'authenticated' && (
          <button
            className={linkClass}
            disabled={signingOut}
            onClick={() => void logout()}
          >
            {signingOut ? 'Logging out…' : 'Log out'}
          </button>
        )}
      </header>

      <main className="flex flex-1 flex-col justify-center py-12 sm:py-20">
        {logoutError && session.status === 'authenticated' && (
          <p role="alert" className="mb-4 text-[#852a24]">
            {logoutError}
          </p>
        )}
        {session.status === 'loading' && (
          <p role="status">Checking your session…</p>
        )}
        {session.status === 'error' && (
          <section>
            <h1 className="mb-4 font-serif text-4xl">
              Unable to check your session
            </h1>
            <p role="alert" className="mb-5">
              {session.message}
            </p>
            <button className={buttonClass} onClick={refreshSession}>
              Try again
            </button>
          </section>
        )}
        {session.status === 'guest' && page === 'welcome' && (
          <section className="max-w-4xl rounded-[2rem] border border-[#d7e1d6] bg-[#eef3e9] px-6 py-12 sm:px-14 sm:py-16 lg:px-20">
            <p className="mb-6 inline-block rounded-full bg-[#dce8dc] px-4 py-2 text-sm font-semibold text-[#244c3e]">
              In development
            </p>
            <h1 className="max-w-[15ch] font-serif text-4xl leading-[1.08] tracking-tight sm:text-6xl lg:text-7xl">
              Staff rostering for Australian hospitality
            </h1>
            <p className="mt-6 max-w-[48ch] leading-relaxed text-[#40564c] sm:text-lg">
              We’re building Rostaroo to help cafés and restaurants plan weekly
              rosters and give staff one place to check shifts and share
              availability.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-5">
              <button
                className={buttonClass}
                onClick={() => setPage('register')}
              >
                Create an owner account
              </button>
              <button className={linkClass} onClick={() => setPage('login')}>
                Log in
              </button>
            </div>
          </section>
        )}
        {session.status === 'guest' && page !== 'welcome' && (
          <AuthForm
            key={page}
            mode={page}
            onLogin={refreshSession}
            onSwitch={() => setPage(page === 'login' ? 'register' : 'login')}
          />
        )}
        {session.status === 'authenticated' &&
          (session.organisation ? (
            <section className="max-w-3xl rounded-3xl border border-[#d7e1d6] bg-[#eef3e9] p-6 sm:p-12">
              <p className="mb-3 font-semibold capitalize text-[#40564c]">
                {session.organisation.role} dashboard
              </p>
              <h1 className="break-words font-serif text-4xl tracking-tight sm:text-6xl">
                {session.organisation.name}
              </h1>
              <p className="mt-4 text-[#40564c]">
                {session.organisation.suburb}, {session.organisation.state}
              </p>
              <p className="mt-8 border-t border-[#cbd8cc] pt-5">
                Employee management and rostering are coming in later
                milestones.
              </p>
            </section>
          ) : (
            <OrganisationForm
              onCreated={(organisation) =>
                setSession((current) =>
                  current.status === 'authenticated'
                    ? { status: 'authenticated', organisation }
                    : current,
                )
              }
              onExpired={returnToLogin}
            />
          ))}
      </main>

      <footer className="border-t border-[#cbd8cc] py-6 text-sm text-[#40564c]">
        Adelaide, South Australia
      </footer>
    </div>
  )
}
