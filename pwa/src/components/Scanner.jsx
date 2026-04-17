/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * - fps 20, formatos limitados = deteccion rapida
 * - Flash verde + haptic al detectar
 * - Linea de escaneo animada
 * - Boton de linterna (torch)
 * - Manejo de permiso denegado con instrucciones claras
 */
import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

// Beep corto con Web Audio API — sin archivos de sonido
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(1850, ctx.currentTime)
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.12)
    osc.onended = () => ctx.close()
  } catch (_) {}
}

const FORMATS = [
  Html5QrcodeSupportedFormats.QR_CODE,
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
]

// Detectar si el error es de permiso denegado
function isPermissionError(e) {
  const msg = (e?.message ?? e?.toString() ?? '').toLowerCase()
  return (
    e?.name === 'NotAllowedError' ||
    e?.name === 'PermissionDeniedError' ||
    msg.includes('permission') ||
    msg.includes('notallowed') ||
    msg.includes('denied')
  )
}

export default function Scanner({ onScan, active = true }) {
  const containerId  = 'qr-scanner-container'
  const onScanRef    = useRef(onScan)
  const trackRef     = useRef(null)
  const [flash,     setFlash]     = useState(false)
  const [torch,     setTorch]     = useState(false)
  const [hasTorch,  setHasTorch]  = useState(false)
  const [camError,  setCamError]  = useState(null) // null | 'denied' | 'unavailable'
  const [retryKey,  setRetryKey]  = useState(0)   // incrementar = reintentar
  onScanRef.current = onScan

  useEffect(() => {
    const track = trackRef.current
    if (!track?.applyConstraints) return
    track.applyConstraints({ advanced: [{ torch }] }).catch(() => {})
  }, [torch])

  useEffect(() => {
    if (!active) {
      setTorch(false)
      setHasTorch(false)
      setCamError(null)
      trackRef.current = null
    }
  }, [active])

  useEffect(() => {
    if (!active) return
    setCamError(null) // limpiar error al reintentar

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

        const boxW = Math.min(Math.round(window.innerWidth * 0.72), 290)
        const boxH = Math.round(boxW * 0.58)

        await scanner.start(
          { facingMode: 'environment' },
          { fps: 20, qrbox: { width: boxW, height: boxH }, aspectRatio: 1.6, disableFlip: false },
          (decoded) => {
            if (!alive) return
            beep()
            if (navigator.vibrate) navigator.vibrate(55)
            setFlash(true)
            setTimeout(() => setFlash(false), 280)
            onScanRef.current(decoded)
          }
        )

        try {
          const video = document.getElementById(containerId)?.querySelector('video')
          const track = video?.srcObject?.getVideoTracks?.()[0]
          if (track?.applyConstraints) {
            trackRef.current = track
            await track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }).catch(() => {})
            const caps = track.getCapabilities?.()
            if (caps?.torch) setHasTorch(true)
          }
        } catch (_) {}

      } catch (e) {
        if (!alive) return
        console.warn('Scanner error:', e)
        setCamError(isPermissionError(e) ? 'denied' : 'unavailable')
      }
    }

    start()

    return () => {
      alive = false
      setTorch(false)
      trackRef.current = null
      if (scanner) {
        scanner.stop().catch(() => {})
        scanner = null
      }
    }
  }, [active, retryKey])

  // ── Pantalla de error ──────────────────────────────
  if (camError) {
    const isDenied = camError === 'denied'
    return (
      <div className="w-full h-full bg-gray-950 flex flex-col items-center justify-center px-8 text-center gap-5">
        <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center text-4xl">
          {isDenied ? '🚫' : '📷'}
        </div>

        <div>
          <p className="text-white font-semibold text-lg mb-1">
            {isDenied ? 'Cámara bloqueada' : 'Cámara no disponible'}
          </p>
          <p className="text-white/50 text-sm leading-relaxed">
            {isDenied
              ? 'Esta app necesita acceso a la cámara para escanear códigos.'
              : 'No se pudo acceder a la cámara. Verifica que ninguna otra app la esté usando.'}
          </p>
        </div>

        {isDenied && (
          <div className="bg-white/5 rounded-2xl px-5 py-4 text-left w-full">
            <p className="text-white/70 text-xs font-semibold uppercase tracking-wide mb-2">
              Cómo activarla en iPhone
            </p>
            <ol className="text-white/50 text-sm space-y-1 list-decimal list-inside">
              <li>Abre <span className="text-white/70">Ajustes</span></li>
              <li>Baja hasta <span className="text-white/70">Safari</span></li>
              <li>Toca <span className="text-white/70">Cámara → Permitir</span></li>
              <li>Vuelve aquí y recarga la página</li>
            </ol>
          </div>
        )}

        <button
          onClick={() => setRetryKey(k => k + 1)}
          className="bg-brand-700 text-white font-semibold px-8 py-3 rounded-xl active:bg-brand-800"
        >
          Intentar de nuevo
        </button>
      </div>
    )
  }

  // ── Vista normal ───────────────────────────────────
  return (
    <div className="relative w-full h-full overflow-hidden bg-black">
      <div id={containerId} className="w-full h-full" />

      <div className={`absolute inset-0 pointer-events-none transition-opacity duration-150
        bg-green-400/35 ${flash ? 'opacity-100' : 'opacity-0'}`} />

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="relative w-72 h-44">
          <span className="absolute top-0 left-0   w-7 h-7 border-t-[3px] border-l-[3px] border-white rounded-tl-md" />
          <span className="absolute top-0 right-0  w-7 h-7 border-t-[3px] border-r-[3px] border-white rounded-tr-md" />
          <span className="absolute bottom-0 left-0  w-7 h-7 border-b-[3px] border-l-[3px] border-white rounded-bl-md" />
          <span className="absolute bottom-0 right-0 w-7 h-7 border-b-[3px] border-r-[3px] border-white rounded-br-md" />
          <div className="absolute top-2 left-3 right-3 h-[2px] animate-scan
            bg-gradient-to-r from-transparent via-green-400 to-transparent" />
        </div>
      </div>

      {hasTorch && (
        <button
          onClick={() => setTorch(t => !t)}
          className={`absolute top-4 right-4 w-11 h-11 rounded-full flex items-center justify-center
            text-xl transition-all active:scale-90 shadow-lg
            ${torch ? 'bg-yellow-400 text-gray-900' : 'bg-black/40 text-white/70 border border-white/20'}`}
        >
          🔦
        </button>
      )}
    </div>
  )
}
