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
      <div
        className="absolute inset-0 z-10 bg-ink-900/40 backdrop-blur-[2px] animate-fade-in"
        onClick={onClose}
      />

      <div
        ref={sheetRef}
        className="absolute inset-x-0 bottom-0 z-20 bg-surface-0 rounded-t-3xl shadow-float
          flex flex-col animate-slide-up"
        style={{
          maxHeight,
          transform: `translateY(${dragY}px)`,
          transition: dragY === 0 ? 'transform 0.3s cubic-bezier(0.32, 0.72, 0, 1)' : 'none',
          willChange: 'transform',
        }}
      >
        <div
          className="flex justify-center pt-3 pb-2 touch-none cursor-grab active:cursor-grabbing shrink-0"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <div className="w-10 h-1.5 rounded-full bg-surface-300" />
        </div>

        {children}
      </div>
    </>
  )
}
