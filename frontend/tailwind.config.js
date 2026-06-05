/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gold: '#C9A84C',
        'navy-black': '#0D0F1A',
        'dark-surface': '#141726',
        'dark-border': '#2A2D3E',
        'text-primary': '#F0EFE9',
        'text-secondary': '#8A8FA8',
        'accent-blue': '#4F8EF7',
        'success-green': '#2ECC71',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}