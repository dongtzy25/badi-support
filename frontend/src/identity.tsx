/* Who is using the app right now: a support agent or a customer.
 * There is no real login in this assignment, so this is a demo switcher. The
 * identity is sent to the API as headers (see api.ts). Remembered across reloads. */

import { createContext, useContext, useState, type ReactNode } from 'react'

export type Identity = { role: 'agent'; agentId: number } | { role: 'customer'; email: string }

const DEFAULT: Identity = { role: 'agent', agentId: 1 }
const STORAGE_KEY = 'badi-support-identity'

function load(): Identity {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? (JSON.parse(saved) as Identity) : DEFAULT
  } catch {
    return DEFAULT
  }
}

interface IdentityContextValue {
  identity: Identity
  setIdentity: (identity: Identity) => void
}

const IdentityContext = createContext<IdentityContextValue | null>(null)

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setState] = useState<Identity>(load)

  const setIdentity = (next: Identity) => {
    setState(next)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      /* storage unavailable (private mode): keep it in memory only */
    }
  }

  return <IdentityContext.Provider value={{ identity, setIdentity }}>{children}</IdentityContext.Provider>
}

export function useIdentity() {
  const value = useContext(IdentityContext)
  if (!value) throw new Error('useIdentity must be used inside <IdentityProvider>')
  return value
}

/** Stable string for React Query cache keys, so agent and customer data never mix. */
export function identityKey(identity: Identity): string {
  return identity.role === 'agent' ? `agent:${identity.agentId}` : `customer:${identity.email}`
}
