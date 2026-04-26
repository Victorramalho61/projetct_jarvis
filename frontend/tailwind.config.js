/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Palette numérica (usada nas páginas existentes)
        voetur: {
          950: "#061410",
          900: "#0C2D1C",
          800: "#134024",
          700: "#1A5C38",
          600: "#1E7A46",
          500: "#27AE60",
          400: "#52BE80",
          300: "#82E0AA",
          200: "#A9DFBF",
          100: "#D5F5E3",
          50:  "#EAFAF1",
        },
        // Palette semântica (usada nos novos componentes de design)
        brand: {
          ink:   "#0C2D1C",
          ink2:  "#0a2417",
          ink3:  "#082018",
          green: "#1E7A46",
          mid:   "#27AE60",
          soft:  "#EAFAF1",
          deep:  "#1A5C38",
          line:  "#E5E7EB",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(12,45,28,0.04), 0 8px 24px -12px rgba(12,45,28,0.12)",
        pop:  "0 10px 40px -12px rgba(12,45,28,0.25)",
        ring: "0 0 0 4px rgba(39,174,96,0.18)",
      },
    },
  },
  plugins: [],
};
