/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        lk: {
          bg: '#09090b',
          fg: '#fafafa',
          'fg-secondary': '#a1a1aa',
          border: '#27272a',
          'border-strong': '#3f3f46',
          primary: '#6366f1',
          'primary-hover': '#4f46e5',
        },
      },
    },
  },
  plugins: [],
};