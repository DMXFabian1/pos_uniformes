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
    <div className="bg-warning-500 text-white text-center text-sm font-semibold py-2.5 px-4 animate-slide-down safe-area-top">
      <div className="flex items-center justify-center gap-2">
        <span className="w-2 h-2 rounded-full bg-white/80 animate-pulse" />
        Sin conexion con la PC principal
      </div>
    </div>
  )
}
