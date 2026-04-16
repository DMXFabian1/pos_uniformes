/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * Usa html5-qrcode. Llama onScan(texto) al detectar un codigo.
 */
import { useEffect, useRef } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

let scannerInstance = null

export default function Scanner({ onScan, active = true }) {
  const containerId = 'qr-scanner-container'
  const started = useRef(false)

  useEffect(() => {
    if (!active) return

    async function start() {
      if (started.current) return
      try {
        const scanner = new Html5Qrcode(containerId)
        scannerInstance = scanner
        await scanner.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 260, height: 180 } },
          (decoded) => { onScan(decoded) }
        )
        started.current = true
      } catch (e) {
        console.warn('Scanner no disponible:', e)
      }
    }

    start()

    return () => {
      if (scannerInstance && started.current) {
        scannerInstance.stop().catch(() => {})
        scannerInstance = null
        started.current = false
      }
    }
  }, [active, onScan])

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
