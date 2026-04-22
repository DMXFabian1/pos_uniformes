import { useEffect, useState } from 'react'
import { authApi } from '../api/auth'

export default function Banner() {
  const [online, setOnline] = useState(true)

  useEffect(() => {
    let interval
    async function check() {
      try {
        await authApi.health()
        setOnline(true)
      } catch {
        setOnline(false)
      }
    }
    check()
    interval = setInterval(check, 30_000)
    return () => clearInterval(interval)
  }, [])

  if (online) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500 text-white text-center text-sm font-semibold py-2 px-4 shadow">
      Sin conexion con la PC principal — modo lectura
    </div>
  )
}
