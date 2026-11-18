import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api, ApiError } from './api'
import type { Organisation } from './api'

const states = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA']

export const buttonClass =
  'rounded-xl bg-[#244c3e] px-5 py-3 font-semibold text-white hover:bg-[#173b2e] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#244c3e] disabled:opacity-60'

export const linkClass =
  'font-semibold text-[#244c3e] underline decoration-1 underline-offset-4'
const fieldClass =
  'w-full rounded-xl border border-[#91a797] bg-white px-3 py-2.5 font-normal'

export function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : 'Something went wrong. Please try again.'
}

function FormPanel({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="w-full max-w-lg rounded-3xl border border-[#d7e1d6] bg-[#eef3e9] p-6 sm:p-10">
      <h1 className="mb-6 font-serif text-4xl tracking-tight">{title}</h1>
      {children}
    </section>
  )
}

export function AuthForm({
  mode,
  onSwitch,
  onLogin,
}: {
  mode: 'login' | 'register'
  onSwitch: () => void
  onLogin: () => void
}) {
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const isRegistration = mode === 'register'
  const action = isRegistration ? 'Create account' : 'Log in'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email')).trim()
    const password = String(form.get('password'))
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email) || email.length > 254) {
      setError('Enter a valid email address.')
      return
    }
    if (
      !password ||
      password.length > 128 ||
      (isRegistration && password.length < 15)
    ) {
      setError(
        isRegistration
          ? 'Use a password of 15 to 128 characters.'
          : 'Enter your password.',
      )
      return
    }

    setError('')
    setPending(true)
    let registered = false
    try {
      if (isRegistration) {
        await api.register({ email, password })
        registered = true
      }
      await api.login({ email, password })
      onLogin()
    } catch (cause) {
      setError(
        registered
          ? 'Account created. Use the log in form to continue.'
          : errorMessage(cause),
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <FormPanel
      title={
        isRegistration ? 'Create your owner account' : 'Log in to Rostaroo'
      }
    >
      <form
        className="space-y-4"
        noValidate
        onSubmit={submit}
        aria-busy={pending}
      >
        <fieldset className="space-y-4" disabled={pending}>
          <label className="block space-y-1 font-semibold">
            <span>Email address</span>
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              className={fieldClass}
            />
          </label>
          <label className="block space-y-1 font-semibold">
            <span>Password</span>
            <input
              name="password"
              type="password"
              autoComplete={
                isRegistration ? 'new-password' : 'current-password'
              }
              aria-describedby={isRegistration ? 'password-help' : undefined}
              required
              className={fieldClass}
            />
          </label>
        </fieldset>
        {isRegistration && (
          <p id="password-help" className="text-sm">
            Use 15 to 128 characters.
          </p>
        )}
        {error && (
          <p role="alert" className="text-[#852a24]">
            {error}
          </p>
        )}
        <button className={buttonClass} disabled={pending} type="submit">
          {pending
            ? isRegistration
              ? 'Creating account…'
              : 'Logging in…'
            : action}
        </button>
      </form>
      <button
        className={`${linkClass} mt-5 block`}
        disabled={pending}
        onClick={onSwitch}
      >
        {isRegistration
          ? 'Already have an account? Log in'
          : 'Create an owner account'}
      </button>
    </FormPanel>
  )
}

export function OrganisationForm({
  onCreated,
  onExpired,
}: {
  onCreated: (organisation: Organisation) => void
  onExpired: () => void
}) {
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const name = String(form.get('name')).trim()
    const suburb = String(form.get('suburb')).trim()
    const state = String(form.get('state'))
    if (
      name.length < 2 ||
      name.length > 100 ||
      suburb.length < 2 ||
      suburb.length > 80 ||
      !states.includes(state)
    ) {
      setError(
        'Enter a business name, suburb and Australian state or territory.',
      )
      return
    }
    setError('')
    setPending(true)
    try {
      onCreated(await api.createOrganisation({ name, suburb, state }))
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        onExpired()
      } else {
        setError(errorMessage(cause))
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <FormPanel title="Set up your organisation">
      <form
        className="space-y-4"
        noValidate
        onSubmit={submit}
        aria-busy={pending}
      >
        <fieldset className="space-y-4" disabled={pending}>
          <label className="block space-y-1 font-semibold">
            <span>Business name</span>
            <input
              name="name"
              autoComplete="organization"
              required
              className={fieldClass}
            />
          </label>
          <label className="block space-y-1 font-semibold">
            <span>Suburb</span>
            <input
              name="suburb"
              autoComplete="address-level2"
              required
              className={fieldClass}
            />
          </label>
          <label className="block space-y-1 font-semibold">
            <span>State or territory</span>
            <select
              name="state"
              autoComplete="address-level1"
              defaultValue=""
              required
              className={fieldClass}
            >
              <option value="" disabled>
                Select a state or territory
              </option>
              {states.map((state) => (
                <option key={state}>{state}</option>
              ))}
            </select>
          </label>
        </fieldset>
        {error && (
          <p role="alert" className="text-[#852a24]">
            {error}
          </p>
        )}
        <button className={buttonClass} disabled={pending} type="submit">
          {pending ? 'Creating organisation…' : 'Create organisation'}
        </button>
      </form>
    </FormPanel>
  )
}
