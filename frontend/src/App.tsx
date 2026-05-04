import { ThemeToggle } from "./components/ThemeToggle";
import { ThemeProvider } from "./theme/ThemeProvider";

export default function App() {
  return (
    <ThemeProvider>
      <div className="min-h-dvh bg-bg-surface text-fg-primary">
        <header className="flex justify-end p-3">
          <ThemeToggle />
        </header>
        <main className="p-4">emerge boot</main>
      </div>
    </ThemeProvider>
  );
}
