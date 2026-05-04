import { useContext } from "react";

import { ThemeContext, type Theme } from "./theme-context";

export type { Theme };

export function useTheme() {
  return useContext(ThemeContext);
}
