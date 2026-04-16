/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * Usa html5-qrcode. Llama onScan(texto) al detectar un codigo.
 */
import { useEffect, useRef } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

export default function Scanner({ onScan, active = true }) {
  const containerId = 'qr-scanner-container'
  const onScanRef = useRef(onScan)
  onScanRef.current = onScan  // siempre fresco sin re-montar el scanner

  useEffect(() => {
    if (!active) return

    let alive = true
    let scanner = null

    async function start() {
      // Pequeña pausa para que cualquier stop previo (StrictMode) termine
      await new Promise(r => setTimeout(r, 120))
      if (!alive) return

      // Limpiar el contenedor por si quedaron restos de una instancia anterior
      const container = document.getElementById(containerId)
      if (container) container.innerHTML = ''

      try {
        scanner = new Html5Qrcode(containerId)
        await scanner.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 260, height: 180 } },
          (decoded) => { if (alive) onScanRef.current(decoded) }
        )
      } catch (e) {
        console.warn('Scanner no disponible:', e)
      }
    }

    start()

    return () => {
      alive = false
      if (scanner) {
        scanner.stop().catch(() => {})
        scanner = null
      }
    }
  }, [active])

  return (
    <div className="relative w-full overflow-hidden rounded-2xl bg-black">
      <div id={containerId} className="w-full" />
      {/* Marco de guia */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-64 h-44 border-2 border-white/70 rounded-xl">
          <span className="absolute top-2 left-2 w-6 h-6 border-t-2 border-l-2 border-white rounded-tl-lg" />
          <span className="absolute top-2 right-2 w-6 h-6 border-t-2 border-r-2 border-white rounded-tr-lg" />
          <span className="absolute bottom-2 left-2 w-6 h-6 border-b-2 border-l-2 border-white rounded-bl-lg" />
          <span className="absolute bottom-2 right-2 w-6 h-6 border-b-2 border-r-2 border-white rounded-br-lg" />
        </div>
      </div>
    </div>
  )
}
