/** @type {import('tailwindcss').Config} */
export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        colors: {
            'ds-blue': '#04f6f6',
            'ds-indigo': '#5610f2',
            'ds-purple': '#f742c1',
            'ds-pink': '#d63394',
            'ds-red': '#c35457',
            'ds-orange': '#ff671f',
            'ds-yellow': '#ffc107',
            'ds-green': '#28b745',
            'ds-teal': '#20c997',
            'ds-cyan': '#17a2b8',
            'ds-black': '#000',
            'ds-white': '#fff',
            'ds-gray': '#6c757d',
            'ds-gray-dark': '#343a40',
            'ds-gray-100': '#f8f9fa',
            'ds-gray-200': '#e9ecef',
            'ds-gray-300': '#dee2e6',
            'ds-gray-400': '#ced4da',
            'ds-gray-500': '#adb5bd',
            'ds-gray-600': '#6c757d',
            'ds-gray-700': '#495057',
            'ds-gray-800': '#343a40',
            'ds-gray-900': '#212529',
            'ds-primary': '#0b3300',
            'ds-secondary': '#fff',
            'ds-success': '#28a745',
            'ds-info': '#17a2b8',
            'ds-warning': '#ffc107',
            'ds-danger': '#dc3545',
            'ds-light': '#f8f9fa',
            'ds-dark': '#343a40'
        }
      },
    },
    plugins: [],
  }