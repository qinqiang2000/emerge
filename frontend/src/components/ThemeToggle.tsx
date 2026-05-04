import { Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";

import { useTheme, type Theme } from "@/theme/useTheme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);

  const opts: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="Theme"
        className="rounded-md border border-border-default bg-bg-elevated px-2 py-1 text-fg-primary"
        onClick={() => setOpen((v) => !v)}
      >
        Theme: {theme}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 rounded-md border border-border-default bg-bg-elevated"
        >
          {opts.map((o) => (
            <button
              key={o.value}
              role="menuitem"
              type="button"
              className="block w-full px-3 py-1 text-left text-fg-primary hover:bg-bg-muted"
              onClick={() => {
                setTheme(o.value);
                setOpen(false);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
