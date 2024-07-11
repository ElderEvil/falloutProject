module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        terminalGreen: '#00ff00',
        terminalBackground: '#000000',
      },
      fontFamily: {
        mono: ['"Courier New"', 'monospace'],
      },
    },
  },
  plugins: [],
}
