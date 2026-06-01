import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useSession } from '../context/SessionContext'
import PinKeypad from '../components/PinKeypad'
import Spinner from '../components/Spinner'

export default function LoginScreen() {
  const [employees, setEmployees] = useState([])
  const [selected, setSelected]   = useState(null)
  const [pin, setPin]             = useState('')
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [fetching, setFetching]   = useState(true)
  const { login, deviceId }       = useSession()
  const navigate                  = useNavigate()

  useEffect(() => {
    authApi.getEmployees()
      .then(data => {
        setEmployees(data)
        const lastId = localStorage.getItem('pos_last_employee_id')
        if (lastId) {
          const last = data.find(e => String(e.id) === lastId && e.tiene_pin)
          if (last) setSelected(last)
        }
      })
      .catch(() => setError('No se pudo conectar con la PC principal.'))
      .finally(() => setFetching(false))
  }, [])

  async function handleLogin() {
    if (!selected || pin.length < 4) return
    setLoading(true)
    setError('')
    try {
      const data = await authApi.login(selected.id, pin, deviceId)
      localStorage.setItem('pos_last_employee_id', String(selected.id))
      login(data)
      navigate('/scanner', { replace: true })
    } catch (e) {
      setError(e.message ?? 'PIN incorrecto.')
      setPin('')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-700">
      <Spinner className="text-white" size="lg" />
      <p className="mt-4 text-white/60 text-sm">Conectando...</p>
    </div>
  )

  return (
    <div className="min-h-screen bg-brand-700 flex flex-col safe-area-top">
      <div className="flex flex-col items-center pt-14 pb-8 px-6">
        <div className="w-16 h-16 bg-white/10 backdrop-blur-sm rounded-3xl flex items-center justify-center mb-5 shadow-lg border border-white/10">
          <span className="text-3xl">U</span>
        </div>
        <h1 className="text-white text-xl font-bold tracking-tight">POS Uniformes</h1>
        <p className="text-white/50 text-sm mt-1.5">
          {selected ? 'Ingresa tu PIN' : 'Selecciona tu nombre'}
        </p>
      </div>

      <div className="flex-1 bg-surface-0 rounded-t-[32px] px-6 pt-8 pb-6 overflow-auto shadow-[0_-4px_32px_rgba(0,0,0,0.1)]">
        {!selected ? (
          <>
            <h2 className="text-ink-700 font-bold text-base mb-4">Quien eres?</h2>
            {employees.length === 0 ? (
              <p className="text-center text-ink-400 py-8 text-sm">No hay empleadas activas con PIN configurado.</p>
            ) : (
              <div className="space-y-2.5">
                {employees.filter(e => e.tiene_pin).map(emp => (
                  <button
                    key={emp.id}
                    onClick={() => { setSelected(emp); setPin('') }}
                    className="w-full flex items-center gap-3.5 p-4 rounded-2xl border border-surface-300
                      active:bg-brand-50 active:border-brand-300 active:scale-[0.98] transition-all text-left touch-target"
                  >
                    <div className="w-11 h-11 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-sm shrink-0">
                      {emp.nombre_visible.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                    <span className="font-semibold text-ink-900">{emp.nombre_visible}</span>
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-8">
              <button
                onClick={() => { setSelected(null); setPin(''); setError('') }}
                className="btn-ghost text-sm px-3 py-2"
              >
                <svg className="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
                Cambiar
              </button>
              <div className="flex items-center gap-2.5 ml-auto">
                <div className="w-9 h-9 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-xs">
                  {selected.nombre_visible.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                </div>
                <span className="font-semibold text-ink-900 text-sm">{selected.nombre_visible}</span>
              </div>
            </div>

            {error && (
              <div className="mb-5 bg-danger-50 border border-danger-100 text-danger-500 rounded-2xl px-4 py-3 text-sm text-center font-medium">
                {error}
              </div>
            )}

            <PinKeypad
              value={pin}
              onChange={setPin}
              onSubmit={handleLogin}
              loading={loading}
            />
          </>
        )}
      </div>
    </div>
  )
}
