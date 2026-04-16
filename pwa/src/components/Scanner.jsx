/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * Usa html5-qrcode. Llama onScan(texto) al detectar un codigo.
 */
import { useEffect, useRef } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

export default function Scanner({ onScan, active = true }) {
  const containerId = 'qr-scanner-container'
  const scannerRef = useRef(null)
  const stoppingRef = useRef(false)

  useEffect(() => {
    if (!active) return

    let cancelled = false

    async function start() {
      // Esperar si hay una parada en curso
      while (stoppingRef.current) {
        await new Promise(r => setTimeout(r, 50))
      }
      if (cancelled) return

      try {
        const scanner = new Html5Qrcode(containerId)
        scannerRef.current = scanner
        await scanner.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 260, height: 180 } },
          (decoded) => { if (!cancelled) onScan(decoded) }
        )
      } catch (e) {
        console.warn('Scanner no disponible:', e)
      }
    }

    start()

    return () => {
      cancelled = true
      const scanner = scannerRef.current
      if (!scanner) return
      scannerRef.current = null
      stoppingRef.current = true
      scanner.stop()
        .catch(() => {})
        .finally(() => { stoppingRef.current = false })
    }
  }, [active]) // onScan intencionalmente excluido para evitar reinicios

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
