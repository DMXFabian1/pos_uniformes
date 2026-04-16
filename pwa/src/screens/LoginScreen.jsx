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
      .then(setEmployees)
      .catch(() => setError('No se pudo conectar con la PC principal.'))
      .finally(() => setFetching(false))
  }, [])

  async function handleLogin() {
    if (!selected || pin.length < 4) return
    setLoading(true)
    setError('')
    try {
      const data = await authApi.login(selected.id, pin, deviceId)
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
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-800">
      <Spinner className="text-white" />
      <p className="mt-4 text-white/70 text-sm">Conectando…</p>
    </div>
  )

  return (
    <div className="min-h-screen bg-brand-800 flex flex-col">
      {/* Header */}
      <div className="flex flex-col items-center pt-12 pb-6 px-6">
        <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mb-4">
          <span className="text-3xl">👕</span>
        </div>
        <h1 className="text-white text-xl font-bold">POS Uniformes</h1>
        <p className="text-white/60 text-sm mt-1">Selecciona tu nombre y escribe tu PIN</p>
      </div>

      {/* Tarjeta principal */}
      <div className="flex-1 bg-white rounded-t-3xl px-6 pt-8 pb-6 overflow-auto">
        {/* Lista de empleadas */}
        {!selected ? (
          <>
            <h2 className="text-gray-700 font-semibold mb-3">¿Quién eres?</h2>
            {employees.length === 0 ? (
              <p className="text-center text-gray-400 py-8">No hay empleadas activas con PIN configurado.</p>
            ) : (
              <div className="space-y-2">
                {employees.filter(e => e.tiene_pin).map(emp => (
                  <button
                    key={emp.id}
                    onClick={() => { setSelected(emp); setPin('') }}
                    className="w-full flex items-center gap-3 p-4 rounded-2xl border border-gray-200 active:bg-brand-50 active:border-brand-300 transition-colors text-left"
                  >
                    <div className="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-sm shrink-0">
                      {emp.nombre_visible.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                    <span className="font-medium text-gray-800">{emp.nombre_visible}</span>
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          /* PIN keypad */
          <>
            <div className="flex items-center gap-3 mb-6">
              <button
                onClick={() => { setSelected(null); setPin(''); setError('') }}
                className="text-brand-600 text-sm font-medium"
              >
                ← Cambiar
              </button>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold text-xs">
                  {selected.nombre_visible.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                </div>
                <span className="font-semibold text-gray-800">{selected.nombre_visible}</span>
              </div>
            </div>

            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm text-center">
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
