/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#fff9f5',
          100: '#f9f0e8',
          150: '#f4e8dc',
          200: '#ead7c8',
          300: '#d8c0aa',
          400: '#c69367',
          500: '#bb613c',
          600: '#a84f2d',
          700: '#8a4326',
          800: '#6f331d',
          900: '#4a3020',
        },
        surface: {
          0:   '#fffdf8',
          50:  '#fdfaf4',
          100: '#f5f0ea',
          200: '#ebe4db',
          300: '#ddd4c8',
          400: '#c9b5a5',
        },
        ink: {
          900: '#1f1f1b',
          700: '#4a3728',
          500: '#6d665e',
          400: '#8a7a6a',
          300: '#a39a90',
          200: '#c9b5a5',
        },
        success: {
          50:  '#eef8f2',
          100: '#daf2e5',
          500: '#27703f',
          600: '#245241',
        },
        danger: {
          50:  '#fff4f1',
          100: '#f5e8e0',
          500: '#c0392b',
          600: '#9a2f22',
        },
        warning: {
          50:  '#fff9ec',
          100: '#f5edda',
          500: '#8a5a00',
          600: '#3d2600',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Avenir Next"', '"Segoe UI"', 'Roboto', 'sans-serif']
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
        '4xl': '32px',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(74, 48, 32, 0.06), 0 4px 12px rgba(74, 48, 32, 0.04)',
        'card-hover': '0 2px 8px rgba(74, 48, 32, 0.1), 0 8px 24px rgba(74, 48, 32, 0.06)',
        'float': '0 8px 32px rgba(74, 48, 32, 0.12), 0 2px 8px rgba(74, 48, 32, 0.06)',
        'toast': '0 4px 24px rgba(31, 31, 27, 0.15)',
      },
      animation: {
        'scan': 'scan 2s ease-in-out infinite',
        'slide-up': 'slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-down': 'slideDown 0.25s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'ready-pulse': 'readyPulse 0.6s ease-out',
        'shimmer': 'shimmer 1.5s infinite',
        'toast-in': 'toastIn 0.35s cubic-bezier(0.32, 0.72, 0, 1)',
        'toast-out': 'toastOut 0.25s ease-in forwards',
        'pop': 'pop 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
      },
      keyframes: {
        scan: {
          '0%, 100%': { transform: 'translateY(0px)', opacity: '0.9' },
          '50%':       { transform: 'translateY(120px)', opacity: '0.5' },
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
        },
        slideDown: {
          '0%':   { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        toastIn: {
          '0%':   { transform: 'translateY(20px) scale(0.95)', opacity: '0' },
          '100%': { transform: 'translateY(0) scale(1)', opacity: '1' },
        },
        toastOut: {
          '0%':   { transform: 'translateY(0) scale(1)', opacity: '1' },
          '100%': { transform: 'translateY(10px) scale(0.95)', opacity: '0' },
        },
        pop: {
          '0%':   { transform: 'scale(0.9)', opacity: '0' },
          '50%':  { transform: 'scale(1.05)' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      }
    }
  },
  plugins: []
}
