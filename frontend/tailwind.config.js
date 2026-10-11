/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          accent: '#FF0053',
          light: '#FC3777',
          lighter: '#FFD6E4',
        },
        secondary: {
          dark: '#310F53',
          base: '#520978',
          light: '#8A83D1',
        },
        neutral: {
          dark: '#1C1D22',
          white: '#FFFFFF',
        },
      },
      fontFamily: {
        sans: ['Montserrat', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
