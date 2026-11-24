export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: '#fefaf6',
          raised: '#f8f1eb',
        },
        ink: {
          DEFAULT: '#1b140e',
          strong: '#180f08',
          soft: '#5c534c',
        },
        brand: {
          DEFAULT: '#00e7ff',
          deep: '#005c66',
          wash: '#daf8fd',
        },
        butter: '#f3e7c9',
        slate: {
          50: '#fefaf6',
          100: '#f8f1eb',
          200: '#e8ded5',
          300: '#d7cbc0',
          400: '#9b8d83',
          500: '#5c534c',
          600: '#3d2e24',
          700: '#2f241c',
          800: '#1b140e',
          900: '#1b140e',
          950: '#180f08',
        },
        sky: {
          50: '#daf8fd',
          100: '#daf8fd',
          200: '#95cbe3',
          300: '#00e7ff',
          400: '#00e7ff',
          500: '#00e7ff',
          600: '#1b140e',
          700: '#180f08',
          800: '#180f08',
          900: '#180f08',
          950: '#180f08',
        },
      },
      fontFamily: {
        sans: ['Satoshi', 'Satoshi Fallback', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Hedvig Letters Serif', 'Hedvig Letters Serif Fallback', 'ui-serif', 'Georgia', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        frame: '20px',
        photo: '14px',
      },
      boxShadow: {
        card: '0 2px 4px 0 rgba(0, 0, 0, 0.04)',
        'card-lifted': '0 4px 8px 0 rgba(0, 0, 0, 0.08)',
      },
    },
  },
  plugins: [],
};
