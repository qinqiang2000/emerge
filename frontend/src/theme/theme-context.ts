import { createContext } from "react";

export type Theme = "light" | "dark" | "system";

export type ThemeContextValue = { theme: Theme; setTheme: (t: Theme) => void };

export const ThemeContext = createContext<ThemeContextValue>({
  theme: "system",
  setTheme: () => {},
});
