/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./RPAChat.App/Components/**/*.{razor,html}",
    "./RPAChat.App/wwwroot/index.html"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["OpenSansRegular", "Segoe UI", "Arial", "sans-serif"]
      }
    }
  },
  plugins: []
};
