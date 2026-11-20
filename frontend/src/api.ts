export type Organisation = {
  id: string
  name: string
  suburb: string
  state: string
  role: 'owner' | 'manager' | 'employee'
}

export type OrganisationInput = Pick<Organisation, 'name' | 'suburb' | 'state'>

type Credentials = { email: string; password: string }

const hostname = window.location.hostname
const apiOrigin =
  import.meta.env.VITE_API_ORIGIN ??
  (['localhost', '127.0.0.1'].includes(hostname)
    ? `http://${hostname}:8000`
    : '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(
  path: string,
  {
    post = false,
    body,
    signal,
  }: { post?: boolean; body?: object; signal?: AbortSignal } = {},
): Promise<T> {
  let response
  try {
    response = await fetch(`${apiOrigin}/api${path}`, {
      method: post ? 'POST' : 'GET',
      credentials: 'include',
      headers: post
        ? { 'Content-Type': 'application/json', 'X-Rostaroo-CSRF': '1' }
        : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(
      0,
      'Could not reach Rostaroo. Check your connection and try again.',
    )
  }
  if (!response.ok) {
    const result = await response.json().catch(() => null)
    const message =
      response.status < 500 && typeof result?.detail === 'string'
        ? result.detail
        : 'Something went wrong. Please try again.'
    throw new ApiError(response.status, message)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  register: (body: Credentials) =>
    request('/auth/register', { post: true, body }),
  login: (body: Credentials) => request('/auth/login', { post: true, body }),
  logout: () => request<void>('/auth/logout', { post: true }),
  me: (signal?: AbortSignal) => request('/auth/me', { signal }),
  organisations: (signal?: AbortSignal) =>
    request<Organisation[]>('/organisations', { signal }),
  createOrganisation: (body: OrganisationInput) =>
    request<Organisation>('/organisations', { post: true, body }),
}

export type InvitationRole = 'manager' | 'employee'

export type TeamMember = {
  id: string
  email: string
  role: Organisation['role']
}

export type Invitation = {
  id: string
  invited_email: string
  invited_role: InvitationRole
  expires_at: string
}

export type CreatedInvitation = Invitation & { code: string }

export const teamApi = {
  members: (id: string, signal?: AbortSignal) =>
    request<TeamMember[]>(`/organisations/${id}/members`, { signal }),
  invitations: (id: string, signal?: AbortSignal) =>
    request<Invitation[]>(`/organisations/${id}/invitations`, { signal }),
  invite: (id: string, body: { email: string; role: InvitationRole }) =>
    request<CreatedInvitation>(`/organisations/${id}/invitations`, {
      post: true,
      body,
    }),
  revoke: (organisationId: string, invitationId: string) =>
    request<void>(
      `/organisations/${organisationId}/invitations/${invitationId}/revoke`,
      { post: true },
    ),
  accept: (code: string) =>
    request<Organisation>('/invitations/accept', {
      post: true,
      body: { code },
    }),
}
