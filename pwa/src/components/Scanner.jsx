/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * - fps 20, formatos limitados = deteccion rapida
 * - Flash verde + haptic al detectar
 * - Linea de escaneo animada
 */
import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

// Solo los formatos que usamos — ignorar el resto acelera mucho el decode
const FORMATS = [
  Html5QrcodeSupportedFormats.QR_CODE,
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
]

export default function Scanner({ onScan, active = true }) {
  const containerId = 'qr-scanner-container'
  const onScanRef   = useRef(onScan)
  const [flash, setFlash] = useState(false)
  onScanRef.current = onScan

  useEffect(() => {
    if (!active) return

    let alive   = true
    let scanner = null

    async function start() {
      await new Promise(r => setTimeout(r, 120))
      if (!alive) return

      const container = document.getElementById(containerId)
      if (container) container.innerHTML = ''

      try {
        scanner = new Html5Qrcode(containerId, {
          formatsToSupport: FORMATS,
          verbose: false,
        })

        // qrbox responsivo al ancho de pantalla
        const boxW = Math.min(Math.round(window.innerWidth * 0.72), 290)
        const boxH = Math.round(boxW * 0.58)

        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 20,
            qrbox: { width: boxW, height: boxH },
            aspectRatio: 1.6,
            disableFlip: false,
          },
          (decoded) => {
            if (!alive) return
            if (navigator.vibrate) navigator.vibrate(55)
            setFlash(true)
            setTimeout(() => setFlash(false), 280)
            onScanRef.current(decoded)
          }
        )

        // Aplicar foco continuo sobre la pista de video activa
        try {
          const video = document.getElementById(containerId)?.querySelector('video')
          const track = video?.srcObject?.getVideoTracks?.()[0]
          if (track?.applyConstraints) {
            await track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] })
          }
        } catch (_) { /* no soportado en este dispositivo, ignorar */ }

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
    <div className="relative w-full h-full overflow-hidden bg-black">
      {/* Video del scanner */}
      <div id={containerId} className="w-full h-full" />

      {/* Flash verde en deteccion */}
      <div
        className={`absolute inset-0 pointer-events-none transition-opacity duration-150
          bg-green-400/35 ${flash ? 'opacity-100' : 'opacity-0'}`}
      />

      {/* Marco guia con esquinas y linea animada */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="relative w-72 h-44">
          {/* Esquinas */}
          <span className="absolute top-0 left-0   w-7 h-7 border-t-[3px] border-l-[3px] border-white rounded-tl-md" />
          <span className="absolute top-0 right-0  w-7 h-7 border-t-[3px] border-r-[3px] border-white rounded-tr-md" />
          <span className="absolute bottom-0 left-0  w-7 h-7 border-b-[3px] border-l-[3px] border-white rounded-bl-md" />
          <span className="absolute bottom-0 right-0 w-7 h-7 border-b-[3px] border-r-[3px] border-white rounded-br-md" />

          {/* Linea de escaneo */}
          <div className="absolute top-2 left-3 right-3 h-[2px] animate-scan
            bg-gradient-to-r from-transparent via-green-400 to-transparent" />
        </div>
      </div>
    </div>
  )
}
