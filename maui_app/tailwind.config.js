/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./RPAChat.App/Components/**/*.{razor,html}",
    "./RPAChat.App/Styles/**/*.css",
    "./RPAChat.App/wwwroot/index.html"
  ],
  theme: {
    extend: {
      colors: {
        rpa: {
          bg0: "#080909",
          bg1: "#0d0f0f",
          panel: "#101313",
          text: "#f4f7f6",
          muted: "#9aa5a3",
          faint: "#5f6a68",
          cyan: "#57f5df",
          cyan2: "#38cdbd",
          amber: "#f5b847",
          green: "#7ee787",
          rose: "#fb7185"
        }
      },
      fontFamily: {
        sans: ["Inter", "OpenSansRegular", "Segoe UI", "Arial", "sans-serif"],
        mono: ["Cascadia Mono", "Consolas", "ui-monospace", "monospace"]
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.58", transform: "scale(0.82)" }
        }
      },
      animation: {
        "pulse-dot": "pulse-dot 1.8s ease-in-out infinite"
      }
    }
  },
  plugins: []
};
