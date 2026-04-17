/**
 * BottomSheet reutilizable
 * - Anima entrada desde abajo (slide-up)
 * - Handle superior arrastrable para cerrar
 * - Se cierra al arrastrar >30% de su altura o tocar el overlay
 * - maxHeight configurable (default 55vh = media pantalla aprox)
 */
import { useRef, useState } from 'react'

export default function BottomSheet({ children, onClose, maxHeight = '55vh' }) {
  const sheetRef  = useRef(null)
  const startY    = useRef(0)
  const [dragY, setDragY] = useState(0)

  function onTouchStart(e) {
    startY.current = e.touches[0].clientY
  }

  function onTouchMove(e) {
    const dy = e.touches[0].clientY - startY.current
    if (dy > 0) setDragY(dy)
  }

  function onTouchEnd() {
    const threshold = (sheetRef.current?.offsetHeight ?? 200) * 0.28
    if (dragY > threshold) {
      onClose()
    } else {
      setDragY(0)
    }
  }

  return (
    <>
      {/* Overlay oscuro — toca para cerrar */}
      <div
        className="absolute inset-0 z-10 bg-black/40"
        onClick={onClose}
      />

      {/* Sheet */}
      <div
        ref={sheetRef}
        className="absolute inset-x-0 bottom-0 z-20 bg-white rounded-t-3xl shadow-2xl
          flex flex-col animate-slide-up"
        style={{
          maxHeight,
          transform: `translateY(${dragY}px)`,
          transition: dragY === 0 ? 'transform 0.25s ease-out' : 'none',
          willChange: 'transform',
        }}
      >
        {/* Handle — solo esta zona arrastra */}
        <div
          className="flex justify-center pt-3 pb-1 touch-none cursor-grab active:cursor-grabbing shrink-0"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <div className="w-10 h-1 rounded-full bg-gray-200" />
        </div>

        {children}
      </div>
    </>
  )
}
