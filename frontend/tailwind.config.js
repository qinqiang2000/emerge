/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "bg-surface": "var(--bg-surface)",
        "bg-elevated": "var(--bg-elevated)",
        "bg-muted": "var(--bg-muted)",
        "fg-primary": "var(--fg-primary)",
        "fg-muted": "var(--fg-muted)",
        "fg-inverse": "var(--fg-inverse)",
        "border-default": "var(--border-default)",
        "border-strong": "var(--border-strong)",
        "accent-primary": "var(--accent-primary)",
        "accent-primary-fg": "var(--accent-primary-fg)",
        "status-success": "var(--status-success)",
        "status-warning": "var(--status-warning)",
        "status-error": "var(--status-error)",
        overlay: "var(--overlay)",
      },
      borderRadius: { sm: "4px", md: "6px", lg: "8px" },
    },
  },
  plugins: [],
};
