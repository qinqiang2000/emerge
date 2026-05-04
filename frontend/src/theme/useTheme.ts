import { useContext } from "react";

import { ThemeContext, type Theme } from "./ThemeProvider";

export type { Theme };

export function useTheme() {
  return useContext(ThemeContext);
}
