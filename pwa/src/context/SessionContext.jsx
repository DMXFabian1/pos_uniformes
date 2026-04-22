import { createContext, useContext, useState, useCallback } from 'react'

const STORAGE_KEY = 'pos_session'
const TOKEN_KEY = 'pos_token'
const DEVICE_KEY = 'pos_device_id'

function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveSession(session) {
  if (session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    localStorage.setItem(TOKEN_KEY, session.token)
  } else {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(TOKEN_KEY)
  }
}

const SessionContext = createContext(null)

export function SessionProvider({ children }) {
  const [session, setSession] = useState(loadSession)

  const login = useCallback((data) => {
    const s = {
      token: data.token,
      device_id: data.device_id,
      employee_id: data.employee_id,
      employee_name: data.employee_name,
    }
    saveSession(s)
    localStorage.setItem(DEVICE_KEY, data.device_id)
    setSession(s)
  }, [])

  const logout = useCallback(() => {
    saveSession(null)
    setSession(null)
  }, [])

  const deviceId = localStorage.getItem(DEVICE_KEY) ?? undefined

  return (
    <SessionContext.Provider value={{ session, login, logout, deviceId }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}
