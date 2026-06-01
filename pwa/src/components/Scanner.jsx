/**
 * Componente de camara para escaneo de QR y codigos de barras.
 * - fps 20, formatos limitados = deteccion rapida
 * - Flash verde + haptic + beep al detectar
 * - Linea de escaneo animada
 * - Boton de linterna (torch)
 * - Slider de zoom
 * - Manejo de permiso denegado con instrucciones claras
 */
import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

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
  const containerId = 'qr-scanner-container'
  const onScanRef   = useRef(onScan)
  const trackRef    = useRef(null)
  const [flash,     setFlash]     = useState(false)
  const [ready,     setReady]     = useState(false) // pulso verde "listo"
  const [torch,     setTorch]     = useState(false)
  const [hasTorch,  setHasTorch]  = useState(false)
  const [camError,  setCamError]  = useState(null)
  const [retryKey,  setRetryKey]  = useState(0)
  const [zoom,      setZoom]      = useState(1)
  const [zoomRange, setZoomRange] = useState(null)
  onScanRef.current = onScan

  // Sincronizar torch
  useEffect(() => {
    const track = trackRef.current
    if (!track?.applyConstraints) return
    track.applyConstraints({ advanced: [{ torch }] }).catch(() => {})
  }, [torch])

  // Sincronizar zoom
  useEffect(() => {
    const track = trackRef.current
    if (!track?.applyConstraints || !zoomRange) return
    track.applyConstraints({ advanced: [{ zoom }] }).catch(() => {})
  }, [zoom, zoomRange])

  // Reset al desactivar / pulso "listo" al reactivar
  const prevActiveRef = useRef(false)
  useEffect(() => {
    if (!active) {
      setTorch(false)
      setHasTorch(false)
      setCamError(null)
      setZoom(1)
      setZoomRange(null)
      trackRef.current = null
    } else if (!prevActiveRef.current && active) {
      // Acaba de reactivarse — mostrar pulso verde
      setReady(true)
      setTimeout(() => setReady(false), 700)
    }
    prevActiveRef.current = active
  }, [active])

  useEffect(() => {
    if (!active) return
    setCamError(null)

    let alive   = true
    let scanner = null

    async function start() {
      await new Promise(r => setTimeout(r, 60))
      if (!alive) return

      const container = document.getElementById(containerId)
      if (container) container.innerHTML = ''

      try {
        scanner = new Html5Qrcode(containerId, {
          formatsToSupport: FORMATS,
          verbose: false,
          experimentalFeatures: {
            useBarCodeDetector: true, // BarcodeDetector nativo en Android Chrome (3-5x mas rapido)
          },
        })

        // Caja pequeña = menos píxeles por frame = detección más rápida
        const boxW = Math.min(Math.round(window.innerWidth * 0.52), 210)
        const boxH = Math.round(boxW * 0.62)

        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 30,
            qrbox: { width: boxW, height: boxH },
            aspectRatio: 1.5,
            disableFlip: true,
            videoConstraints: {
              facingMode: { ideal: 'environment' },
              width:  { ideal: 1280 },
              height: { ideal: 720 },
            },
          },
          (decoded) => {
            if (!alive) return
            beep()
            if (navigator.vibrate) navigator.vibrate(55)
            setFlash(true)
            setTimeout(() => setFlash(false), 280)
            onScanRef.current(decoded)
          },
          () => {
            // onError silencioso — dispara el pulso de "listo" continuamente
          }
        )

        try {
          const video = document.getElementById(containerId)?.querySelector('video')
          const track = video?.srcObject?.getVideoTracks?.()[0]
          if (track?.applyConstraints) {
            trackRef.current = track
            const caps = track.getCapabilities?.()
            // Forzar lente principal en iOS (zoom 2x = lente 1x real)
            if (caps?.zoom && caps.zoom.max >= 1) {
              await track.applyConstraints({ advanced: [{ zoom: 1.0 }] }).catch(() => {})
              setZoom(1.0)
            }
            await track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }).catch(() => {})
            if (caps?.torch) setHasTorch(true)
            if (caps?.zoom) {
              setZoomRange({ min: caps.zoom.min, max: caps.zoom.max, step: caps.zoom.step ?? 0.1 })
            }
          }
        } catch (_) {}

      } catch (e) {
        if (!alive) return
        setCamError(isPermissionError(e) ? 'denied' : 'unavailable')
      }
    }

    start()

    return () => {
      alive = false
      setTorch(false)
      setZoom(1)
      setZoomRange(null)
      trackRef.current = null
      if (scanner) { scanner.stop().catch(() => {}); scanner = null }
    }
  }, [active, retryKey])

  // ── Error ──
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
            <p className="text-white/70 text-xs font-semibold uppercase tracking-wide mb-2">Cómo activarla en iPhone</p>
            <ol className="text-white/50 text-sm space-y-1 list-decimal list-inside">
              <li>Abre <span className="text-white/70">Ajustes</span></li>
              <li>Baja hasta <span className="text-white/70">Safari</span></li>
              <li>Toca <span className="text-white/70">Cámara → Permitir</span></li>
              <li>Vuelve aquí y recarga la página</li>
            </ol>
          </div>
        )}
        <button onClick={() => setRetryKey(k => k + 1)} className="bg-brand-700 text-white font-semibold px-8 py-3 rounded-xl active:bg-brand-800">
          Intentar de nuevo
        </button>
      </div>
    )
  }

  // ── Vista normal ──
  return (
    <div className="relative w-full h-full overflow-hidden bg-black">
      <div id={containerId} className="w-full h-full" />

      {/* Flash */}
      <div className={`absolute inset-0 pointer-events-none transition-opacity duration-200
        ${flash ? 'opacity-100' : 'opacity-0'}`}
        style={{ background: 'radial-gradient(circle, rgba(168,79,45,0.3) 0%, transparent 70%)' }} />

      {/* Viñeta oscura alrededor del area de escaneo */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 55% 35% at center, transparent 0%, rgba(0,0,0,0.55) 100%)' }} />

      {/* Marco guia */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="relative w-60 h-40">
          {/* Esquinas */}
          {[
            'top-0 left-0 border-t-[3px] border-l-[3px] rounded-tl-xl',
            'top-0 right-0 border-t-[3px] border-r-[3px] rounded-tr-xl',
            'bottom-0 left-0 border-b-[3px] border-l-[3px] rounded-bl-xl',
            'bottom-0 right-0 border-b-[3px] border-r-[3px] rounded-br-xl',
          ].map((cls, i) => (
            <span key={i} className={`absolute w-8 h-8 ${cls} transition-all duration-300
              ${ready ? 'border-brand-400 shadow-[0_0_12px_rgba(168,79,45,0.5)]' : flash ? 'border-brand-400' : 'border-white/80'}`} />
          ))}
          {/* Linea de escaneo */}
          <div className="absolute left-4 right-4 h-[2px] animate-scan rounded-full"
            style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(168,79,45,0.8) 30%, rgba(168,79,45,0.8) 70%, transparent 100%)' }} />
        </div>
      </div>

      {/* Controles superiores */}
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between pointer-events-none">
        <div className="pointer-events-auto" />
        {hasTorch && (
          <button
            onClick={() => setTorch(t => !t)}
            className={`pointer-events-auto w-10 h-10 rounded-full flex items-center justify-center
              transition-all active:scale-90 backdrop-blur-md
              ${torch
                ? 'bg-brand-400 text-white shadow-[0_0_16px_rgba(168,79,45,0.4)]'
                : 'bg-white/10 text-white/70 border border-white/20'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
            </svg>
          </button>
        )}
      </div>

      {/* Zoom slider */}
      {zoomRange && (
        <div className="absolute bottom-5 left-8 right-8 flex items-center gap-3">
          <svg className="w-4 h-4 text-white/40 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
          </svg>
          <input
            type="range"
            min={zoomRange.min}
            max={zoomRange.max}
            step={zoomRange.step}
            value={zoom}
            onChange={e => setZoom(Number(e.target.value))}
            className="flex-1 h-1 accent-brand-400 cursor-pointer"
          />
          <span className="text-white/50 text-xs font-medium w-8 text-right tabular-nums">{zoom.toFixed(1)}x</span>
        </div>
      )}
    </div>
  )
}
