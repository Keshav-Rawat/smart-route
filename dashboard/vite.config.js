/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'traffic-green': '#22c55e',
        'traffic-yellow': '#eab308',
        'traffic-red': '#ef4444',
      },
    },
  },
  plugins: [],
}