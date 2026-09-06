/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // CI-MICOP brand green scale - primary actions, active nav state,
        // links. Use brand-600 as the default "primary" shade.
        brand: {
          50: "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
          300: "#86efac",
          400: "#4ade80",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
          900: "#14532d",
        },
        ink: "#0f172a",       // primary dark text
        muted: "#64748b",     // secondary/muted text
        surface: "#f7f9f8",   // page background
        card: "#ffffff",      // card/panel background
        border: "#e5e7eb",    // default hairline border
        success: "#16a34a",
        warning: "#d97706",
        danger: "#dc2626",
        info: "#2563eb",
      },
      borderRadius: {
        card: "0.75rem",
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
