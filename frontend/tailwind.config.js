/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // CI-MICOP brand blue scale - primary actions, active nav state,
        // links. Use brand-600 as the default "primary" shade (#1D4ED8) and
        // brand-700 for hover. Status colours (success/warning/danger) are
        // separate tokens below - approved/completed stays green.
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af",
          800: "#1e3a8a",
          900: "#172554",
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
