import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, teamApi } from './api'
import type {
  CreatedInvitation,
  Invitation,
  Organisation,
  TeamMember,
} from './api'
import { buttonClass, errorMessage, fieldClass, linkClass } from './Forms'

const panelClass = 'rounded-3xl border border-[#d7e1d6] bg-[#eef3e9] p-6 sm:p-8'
const alertClass = 'text-sm text-[#852a24]'
const expiryFormat = new Intl.DateTimeFormat('en-AU', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

export function OrganisationDashboard({
  organisation,
  onExpired,
}: {
  organisation: Organisation
  onExpired: () => void
}) {
  const [showTeam, setShowTeam] = useState(false)

  return (
    <div className="space-y-6">
      <section className={panelClass}>
        <p className="mb-3 font-semibold capitalize text-[#40564c]">
          {organisation.role} dashboard
        </p>
        <h1 className="break-words font-serif text-4xl tracking-tight sm:text-6xl">
          {organisation.name}
        </h1>
        <p className="mt-4">
          {organisation.suburb}, {organisation.state}
        </p>
        {organisation.role === 'employee' ? (
          <p className="mt-6 border-t border-[#cbd8cc] pt-5">
            Your membership role is <strong>employee</strong>.
          </p>
        ) : (
          <button
            type="button"
            className={`${buttonClass} mt-6`}
            aria-expanded={showTeam}
            aria-controls="team-management"
            onClick={() => setShowTeam(!showTeam)}
          >
            {showTeam ? 'Hide team' : 'Manage team'}
          </button>
        )}
        <p className="mt-5 text-sm text-[#40564c]">
          Rostering is coming in a later milestone.
        </p>
      </section>
      <div id="team-management" hidden={!showTeam}>
        {showTeam && (
          <TeamManagement organisation={organisation} onExpired={onExpired} />
        )}
      </div>
    </div>
  )
}

function TeamManagement({
  organisation,
  onExpired,
}: {
  organisation: Organisation
  onExpired: () => void
}) {
  const [team, setTeam] = useState<{
    members: TeamMember[]
    invitations: Invitation[]
  } | null>(null)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [actionError, setActionError] = useState('')
  const [feedback, setFeedback] = useState('')
  const [pending, setPending] = useState<'invite' | string | null>(null)
  const [created, setCreated] = useState<CreatedInvitation | null>(null)
  const [copyFeedback, setCopyFeedback] = useState('')
  const { id, role } = organisation

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      teamApi.members(id, controller.signal),
      teamApi.invitations(id, controller.signal),
    ])
      .then(([members, invitations]) => {
        if (!controller.signal.aborted) setTeam({ members, invitations })
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        if (cause instanceof ApiError && cause.status === 401) onExpired()
        else setLoadError(errorMessage(cause))
      })
    return () => controller.abort()
  }, [id, attempt, onExpired])

  function handleError(cause: unknown) {
    if (cause instanceof ApiError && cause.status === 401) onExpired()
    else setActionError(errorMessage(cause))
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const email = String(data.get('email')).trim()
    const invitedRole = data.get('role')
    setFeedback('')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email) || email.length > 254) {
      setActionError('Enter a valid email address.')
      return
    }
    if (
      invitedRole !== 'employee' &&
      (invitedRole !== 'manager' || role !== 'owner')
    ) {
      setActionError('Choose an available role.')
      return
    }
    setActionError('')
    setPending('invite')
    try {
      const { code, ...invitation } = await teamApi.invite(id, {
        email,
        role: invitedRole,
      })
      setCreated({ ...invitation, code })
      setCopyFeedback('')
      setTeam(
        (current) =>
          current && {
            ...current,
            invitations: [invitation, ...current.invitations],
          },
      )
      form.reset()
    } catch (cause) {
      handleError(cause)
    } finally {
      setPending(null)
    }
  }

  async function revoke(invitation: Invitation) {
    setActionError('')
    setFeedback('')
    setPending(invitation.id)
    try {
      await teamApi.revoke(id, invitation.id)
      setTeam(
        (current) =>
          current && {
            ...current,
            invitations: current.invitations.filter(
              (item) => item.id !== invitation.id,
            ),
          },
      )
      setCreated((current) => (current?.id === invitation.id ? null : current))
      setFeedback('Invitation revoked.')
    } catch (cause) {
      handleError(cause)
    } finally {
      setPending(null)
    }
  }

  async function copy(code: string) {
    try {
      await navigator.clipboard.writeText(code)
      setCopyFeedback('Invitation code copied.')
    } catch {
      setCopyFeedback(
        'Clipboard access failed. Select and copy the code manually.',
      )
    }
  }

  if (loadError) {
    return (
      <section className={panelClass}>
        <h2 className="font-serif text-2xl">Team management</h2>
        <p role="alert" className={alertClass}>
          {loadError}
        </p>
        <button
          className={`${linkClass} mt-3`}
          onClick={() => {
            setLoadError('')
            setAttempt((current) => current + 1)
          }}
        >
          Try again
        </button>
      </section>
    )
  }
  if (!team) return <p role="status">Loading team…</p>

  return (
    <div className="grid items-start gap-6 md:grid-cols-2">
      <section className={panelClass}>
        <h2 className="mb-4 font-serif text-2xl">Team directory</h2>
        {team.members.length ? (
          <ul className="divide-y divide-[#cbd8cc]">
            {team.members.map((member) => (
              <li
                key={member.id}
                className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-3"
              >
                <span className="break-all">{member.email}</span>
                <span className="font-semibold capitalize">{member.role}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No team members yet.</p>
        )}
      </section>
      <section className={panelClass}>
        <h2 className="mb-4 font-serif text-2xl">Invite a team member</h2>
        <form
          noValidate
          onSubmit={invite}
          className="space-y-4"
          aria-busy={pending === 'invite'}
        >
          <fieldset disabled={pending !== null} className="space-y-4">
            <label className="block space-y-1 font-semibold">
              <span>Invitee email</span>
              <input
                className={fieldClass}
                type="email"
                name="email"
                required
              />
            </label>
            <label className="block space-y-1 font-semibold">
              <span>Role</span>
              <select
                className={fieldClass}
                name="role"
                defaultValue="employee"
              >
                <option value="employee">Employee</option>
                {role === 'owner' && <option value="manager">Manager</option>}
              </select>
            </label>
          </fieldset>
          <button
            disabled={pending !== null}
            type="submit"
            className={buttonClass}
          >
            {pending === 'invite'
              ? 'Creating invitation…'
              : 'Create invitation'}
          </button>
        </form>
        {actionError && (
          <p role="alert" className={`${alertClass} mt-4`}>
            {actionError}
          </p>
        )}
        {feedback && (
          <p role="status" className="mt-4">
            {feedback}
          </p>
        )}
        {created && (
          <div className="mt-5 space-y-2 rounded-xl border border-[#91a797] bg-white p-4">
            <p role="status" className="font-semibold">
              Invitation created
            </p>
            <p className="text-sm">
              Share this one-time code privately with {created.invited_email}.
              Copy it before leaving this view.
            </p>
            <code
              className="block break-all select-all"
              aria-label="New invitation code"
            >
              {created.code}
            </code>
            <button
              type="button"
              className={linkClass}
              onClick={() => void copy(created.code)}
            >
              Copy invitation code
            </button>
            {copyFeedback && (
              <p role="status" className="text-sm">
                {copyFeedback}
              </p>
            )}
          </div>
        )}
        <h2 className="mt-8 mb-3 font-serif text-2xl">Pending invitations</h2>
        {team.invitations.length ? (
          <ul className="divide-y divide-[#cbd8cc]">
            {team.invitations.map((invitation) => (
              <li key={invitation.id} className="space-y-1 py-3">
                <p className="break-all font-semibold">
                  {invitation.invited_email}
                </p>
                <p className="text-sm">
                  <span className="capitalize">{invitation.invited_role}</span>
                  {' · Expires '}
                  <time dateTime={invitation.expires_at}>
                    {expiryFormat.format(new Date(invitation.expires_at))}
                  </time>
                </p>
                <button
                  type="button"
                  disabled={pending !== null}
                  className={`${linkClass} disabled:opacity-60`}
                  aria-label={`Revoke invitation for ${invitation.invited_email}`}
                  onClick={() => void revoke(invitation)}
                >
                  {pending === invitation.id ? 'Revoking…' : 'Revoke'}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p>No pending invitations.</p>
        )}
      </section>
    </div>
  )
}

export function JoinOrganisation({
  onJoined,
  onExpired,
}: {
  onJoined: (organisation: Organisation) => void
  onExpired: () => void
}) {
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function accept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const code = String(new FormData(event.currentTarget).get('code')).trim()
    if (!/^[A-Za-z0-9_-]{43}$/u.test(code)) {
      setError('Enter the full invitation code.')
      return
    }
    setError('')
    setPending(true)
    try {
      onJoined(await teamApi.accept(code))
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) onExpired()
      else setError(errorMessage(cause))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className={panelClass}>
      <h2 className="mb-4 font-serif text-3xl">Join a team</h2>
      <p id="join-help" className="mb-4 text-sm">
        Sign in with the email address your team invited and enter the code they
        shared with you.
      </p>
      <form
        noValidate
        onSubmit={accept}
        className="space-y-4"
        aria-busy={pending}
      >
        <label className="block space-y-1 font-semibold">
          <span>Invitation code</span>
          <input
            name="code"
            className={fieldClass}
            required
            disabled={pending}
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="none"
            aria-describedby="join-help"
          />
        </label>
        {error && (
          <p role="alert" className={alertClass}>
            {error}
          </p>
        )}
        <button type="submit" disabled={pending} className={buttonClass}>
          {pending ? 'Joining…' : 'Accept invitation'}
        </button>
      </form>
    </section>
  )
}
