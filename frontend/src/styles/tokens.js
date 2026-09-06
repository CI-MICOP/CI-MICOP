// Mirrors the color tokens in tailwind.config.js as plain JS values, for
// contexts that need real hex codes rather than Tailwind class names
// (e.g. chart libraries added in a later step). Keep both in sync.

export const colors = {
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
  ink: "#0f172a",
  muted: "#64748b",
  surface: "#f7f9f8",
  card: "#ffffff",
  border: "#e5e7eb",
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  info: "#2563eb",
};
