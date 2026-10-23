// Mirrors the color tokens in tailwind.config.js as plain JS values, for
// contexts that need real hex codes rather than Tailwind class names
// (e.g. chart libraries added in a later step). Keep both in sync.

export const colors = {
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
