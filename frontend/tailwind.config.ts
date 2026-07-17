import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: '#1a1f2e',
        'sidebar-hover': '#252b3d',
        brand: '#4f6ef7',
        'brand-dark': '#3d5ce0',
      },
    },
  },
  plugins: [],
} satisfies Config
