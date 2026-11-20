import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import type { Organisation } from './api'
import { OrganisationDashboard } from './Team'

const organisation: Organisation = {
  id: 'synthetic-organisation',
  name: 'Example Cafe',
  suburb: 'Adelaide',
  state: 'SA',
  role: 'owner',
}
const members = [
  { id: 'synthetic-member', email: 'staff@example.com', role: 'employee' },
]
const invitation = {
  id: 'synthetic-invitation',
  invited_email: 'invitee@example.com',
  invited_role: 'employee',
  expires_at: '2030-03-01T00:00:00Z',
}
const code = 'A'.repeat(43)

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status })
}

function mockTeam() {
  const fetchMock = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(json(200, members))
    .mockResolvedValueOnce(json(200, []))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function openTeam(role: Organisation['role'] = 'owner') {
  render(
    <OrganisationDashboard
      organisation={{ ...organisation, role }}
      onExpired={vi.fn()}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Manage team' }))
  await screen.findByRole('heading', { name: 'Team directory' })
}

function enterEmail(email: string) {
  fireEvent.change(screen.getByLabelText('Invitee email'), {
    target: { value: email },
  })
}

function submitInvitation() {
  fireEvent.click(screen.getByRole('button', { name: 'Create invitation' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('renders a team directory and gives owners the manager role option', async () => {
  mockTeam()
  await openTeam()
  const row = screen.getByText('staff@example.com').closest('li')!
  expect(within(row).getByText('employee')).toBeTruthy()
  expect(screen.getByRole('option', { name: 'Manager' })).toBeTruthy()
  expect(screen.getByText('No pending invitations.')).toBeTruthy()
})

it('gives managers only the employee invitation option', async () => {
  mockTeam()
  await openTeam('manager')
  expect(screen.getByRole('option', { name: 'Employee' })).toBeTruthy()
  expect(screen.queryByRole('option', { name: 'Manager' })).toBeNull()
})

it('validates invitation email and shows server errors', async () => {
  const fetchMock = mockTeam().mockResolvedValueOnce(
    json(409, {
      detail: 'A pending invitation already exists for this email.',
    }),
  )
  await openTeam()
  enterEmail('invalid')
  submitInvitation()
  expect(screen.getByRole('alert').textContent).toBe(
    'Enter a valid email address.',
  )
  expect(fetchMock).toHaveBeenCalledTimes(2)
  enterEmail(invitation.invited_email)
  submitInvitation()
  expect(
    (
      await screen.findByText(
        'A pending invitation already exists for this email.',
      )
    ).getAttribute('role'),
  ).toBe('alert')
  expect(screen.queryByText('Invitation created')).toBeNull()
})

it('displays and copies the new code, and removes the pending invitation on revoke', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText: copy } })
  const fetchMock = mockTeam()
    .mockResolvedValueOnce(json(201, { ...invitation, code }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
  await openTeam()
  enterEmail(invitation.invited_email)
  submitInvitation()
  expect(await screen.findByText('Invitation created')).toBeTruthy()
  expect(screen.getByLabelText('New invitation code').textContent).toBe(code)
  expect(screen.getByText(/Expires/).querySelector('time')?.dateTime).toBe(
    invitation.expires_at,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Copy invitation code' }))
  expect(await screen.findByText('Invitation code copied.')).toBeTruthy()
  expect(copy).toHaveBeenCalledWith(code)
  fireEvent.click(
    screen.getByRole('button', {
      name: `Revoke invitation for ${invitation.invited_email}`,
    }),
  )
  expect(await screen.findByText('Invitation revoked.')).toBeTruthy()
  expect(screen.getByText('No pending invitations.')).toBeTruthy()
  expect(screen.queryByLabelText('New invitation code')).toBeNull()
  expect(fetchMock).toHaveBeenLastCalledWith(
    expect.stringContaining('/revoke'),
    expect.objectContaining({ method: 'POST', credentials: 'include' }),
  )
})

it('reports an invalid or expired invitation, then opens the employee view after acceptance', async () => {
  const fetchMock = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(json(200, {}))
    .mockResolvedValueOnce(json(200, []))
    .mockResolvedValueOnce(
      json(400, {
        detail: 'This invitation is invalid or no longer available.',
      }),
    )
    .mockResolvedValueOnce(json(200, { ...organisation, role: 'employee' }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const accept = await screen.findByRole('button', {
    name: 'Accept invitation',
  })
  fireEvent.click(accept)
  expect(screen.getByRole('alert').textContent).toBe(
    'Enter the full invitation code.',
  )
  fireEvent.change(screen.getByLabelText('Invitation code'), {
    target: { value: code },
  })
  fireEvent.click(accept)
  expect(
    await screen.findByText(
      'This invitation is invalid or no longer available.',
    ),
  ).toBeTruthy()
  fireEvent.click(accept)
  expect(
    await screen.findByRole('heading', { name: organisation.name }),
  ).toBeTruthy()
  expect(screen.getByText(/Your membership role is/)).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Manage team' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Create invitation' })).toBeNull()
  expect(fetchMock).toHaveBeenLastCalledWith(
    expect.stringMatching(/\/invitations\/accept$/),
    expect.objectContaining({
      body: JSON.stringify({ code }),
      credentials: 'include',
    }),
  )
})
