import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'

const organisation = {
  id: 'synthetic-organisation',
  name: 'Example Cafe',
  suburb: 'Adelaide',
  state: 'SA',
  role: 'owner',
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status })
}

function mockGuest() {
  return vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(json(401, { detail: 'Please log in.' }))
}

async function openLogin() {
  fireEvent.click(await screen.findByRole('button', { name: 'Log in' }))
}

function enter(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('introduces Rostaroo and withholds the dashboard and onboarding from guests', async () => {
  vi.stubGlobal('fetch', mockGuest())
  render(<App />)

  expect(within(screen.getByRole('banner')).getByText(/^Rostaroo/)).toBeTruthy()
  const main = within(screen.getByRole('main'))
  expect(
    await main.findByRole('heading', {
      level: 1,
      name: 'Staff rostering for Australian hospitality',
    }),
  ).toBeTruthy()
  expect(main.getByText('In development')).toBeTruthy()
  expect(main.queryByText('Owner dashboard')).toBeNull()
  expect(main.queryByText('Set up your organisation')).toBeNull()
})

it('validates registration email and password before sending a request', async () => {
  const fetch = mockGuest()
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  fireEvent.click(
    await screen.findByRole('button', { name: 'Create an account' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
  expect(screen.getByRole('alert').textContent).toBe(
    'Enter a valid email address.',
  )
  enter('Email address', 'owner@example.com')
  enter('Password', 'short')
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
  expect(screen.getByRole('alert').textContent).toBe(
    'Use a password of 15 to 128 characters.',
  )
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('validates login and shows a server-side credential error', async () => {
  const fetch = mockGuest().mockResolvedValueOnce(
    json(401, { detail: 'Email or password is incorrect.' }),
  )
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  await openLogin()
  enter('Email address', 'owner@example.com')
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(screen.getByRole('alert').textContent).toBe('Enter your password.')
  expect(fetch).toHaveBeenCalledTimes(1)
  enter('Password', 'synthetic passphrase')
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(
    (await screen.findByText('Email or password is incorrect.')).getAttribute(
      'role',
    ),
  ).toBe('alert')
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringMatching(/\/auth\/login$/),
    expect.objectContaining({
      credentials: 'include',
      headers: expect.objectContaining({ 'X-Rostaroo-CSRF': '1' }),
    }),
  )
})

it('shows session loading and recovers from a request failure', async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockRejectedValueOnce(new TypeError())
    .mockResolvedValueOnce(json(401, { detail: 'Please log in.' }))
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  expect(screen.getByRole('status').textContent).toBe('Checking your session…')
  expect((await screen.findByRole('alert')).textContent).toMatch(
    /Could not reach Rostaroo/,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('button', { name: 'Log in' })).toBeTruthy()
})

it('restores onboarding, validates its fields and opens the new organisation dashboard', async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(json(200, {}))
    .mockResolvedValueOnce(json(200, []))
    .mockResolvedValueOnce(json(201, organisation))
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  const submit = await screen.findByRole('button', {
    name: 'Create organisation',
  })
  fireEvent.click(submit)
  expect(screen.getByRole('alert').textContent).toMatch(
    /business name, suburb and Australian state/,
  )
  expect(fetch).toHaveBeenCalledTimes(2)
  enter('Business name', organisation.name)
  enter('Suburb', organisation.suburb)
  enter('State or territory', organisation.state)
  fireEvent.click(submit)
  expect(
    await screen.findByRole('heading', { name: organisation.name }),
  ).toBeTruthy()
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringMatching(/\/organisations$/),
    expect.objectContaining({
      credentials: 'include',
      body: JSON.stringify({
        name: organisation.name,
        suburb: organisation.suburb,
        state: organisation.state,
      }),
    }),
  )
})

it('restores a protected dashboard and returns to login after logout', async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(json(200, {}))
    .mockResolvedValueOnce(json(200, [organisation]))
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  expect(
    await screen.findByRole('heading', { name: organisation.name }),
  ).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
  expect(
    await screen.findByRole('heading', { name: 'Log in to Rostaroo' }),
  ).toBeTruthy()
  expect(screen.queryByRole('heading', { name: organisation.name })).toBeNull()
})

it('registers, logs in and loads onboarding for the new account', async () => {
  const fetch = mockGuest()
    .mockResolvedValueOnce(json(201, {}))
    .mockResolvedValueOnce(json(200, {}))
    .mockResolvedValueOnce(json(200, {}))
    .mockResolvedValueOnce(json(200, []))
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  fireEvent.click(
    await screen.findByRole('button', { name: 'Create an account' }),
  )
  enter('Email address', 'owner@example.com')
  enter('Password', 'synthetic registration passphrase')
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
  expect(
    await screen.findByRole('heading', { name: 'Set up your organisation' }),
  ).toBeTruthy()
  expect(fetch.mock.calls.map(([url]) => String(url).split('/api')[1])).toEqual(
    ['/auth/me', '/auth/register', '/auth/login', '/auth/me', '/organisations'],
  )
})
