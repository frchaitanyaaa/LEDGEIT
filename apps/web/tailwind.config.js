/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#141517", 900: "#1d1e21", 800: "#292a2e", 700: "#38393e" },
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
