/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0071e3',
        secondary: '#6e6e73',
        success: '#34c759',
        danger: '#ff3b30',
        warning: '#ff9f0a',
        info: '#0a84ff',
        light: '#f5f5f7',
        dark: '#1d1d1f',
      },
    },
  },
  plugins: [],
}