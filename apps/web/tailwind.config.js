/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#0b1220", 900: "#111a2e", 800: "#1a2540", 700: "#26324f" },
        brand: { 50: "#eef6ff", 100: "#d9eaff", 500: "#2f7cf6", 600: "#1f66d9", 700: "#1a52ad" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
