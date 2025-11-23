import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'matrix-black': '#050505',
        'matrix-card': '#0A0A0A',
        'matrix-green': '#10b981', // Emerald 500
        'matrix-green-dim': '#064e3b', // Emerald 900
        'matrix-border': 'rgba(255, 255, 255, 0.1)',
      },
      boxShadow: {
        'neon-green': '0 0 10px rgba(16, 185, 129, 0.5)',
        'card-hover': '0 0 60px rgba(16, 185, 129, 0.15)',
      },
      keyframes: {
        shimmer: {
          '100%': { transform: 'translateX(200%)' },
        },
        'float-card': {
          '0%, 100%': { transform: 'rotateY(-15deg) rotateX(5deg) translateY(0px)' },
          '50%': { transform: 'rotateY(-15deg) rotateX(5deg) translateY(-15px)' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '50%': { opacity: '1' },
          '100%': { transform: 'translateY(300px)', opacity: '0' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 rgba(16, 185, 129, 0)' },
          '50%': { boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite linear',
        'float-card': 'float-card 6s ease-in-out infinite',
        'scan-line': 'scan-line 3s linear infinite',
        blink: 'blink 1s step-end infinite',
        'pulse-glow': 'pulse-glow 3s infinite',
      },
    },
  },
  plugins: [],
};

export default config;
