/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif']
      },
      animation: {
        scan: 'scan 2s ease-in-out infinite',
        'slide-up': 'slideUp 0.25s ease-out',
        'ready-pulse': 'readyPulse 0.6s ease-out',
      },
      keyframes: {
        scan: {
          '0%, 100%': { transform: 'translateY(0px)', opacity: '0.9' },
          '50%':       { transform: 'translateY(160px)', opacity: '0.6' },
        },
        loading: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
        readyPulse: {
          '0%':   { opacity: '0', transform: 'scale(0.92)' },
          '50%':  { opacity: '1', transform: 'scale(1.06)' },
          '100%': { opacity: '0', transform: 'scale(1)'    },
        },
        slideUp: {
          '0%':   { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        }
      }
    }
  },
  plugins: []
}
