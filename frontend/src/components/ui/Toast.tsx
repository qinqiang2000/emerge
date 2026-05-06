import * as RadixToast from "@radix-ui/react-toast";
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

// Dogfood follow-up #4 + hygiene-tail #13: a tiny, auto-dismiss "Saved"
// pill. Wraps Radix Toast so the call sites only need `toast.show(text)`.
//
// Tests that don't mount <ToastProvider> get a no-op fallback so they
// keep passing without scaffolding — production code paths must wrap the
// app in <ToastProvider> for users to actually see anything.

type ToastEntry = { id: number; message: string };

type ToastContextShape = {
  show: (message: string) => void;
};

const ToastCtx = createContext<ToastContextShape | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const show = useCallback((message: string) => {
    setToasts((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), message },
    ]);
  }, []);
  return (
    <ToastCtx.Provider value={{ show }}>
      <RadixToast.Provider duration={2000} swipeDirection="right">
        {children}
        {toasts.map((t) => (
          <RadixToast.Root
            key={t.id}
            onOpenChange={(open) => {
              if (!open) {
                setToasts((prev) => prev.filter((x) => x.id !== t.id));
              }
            }}
            className="rounded-md border border-border-default bg-bg-elevated px-3 py-2 text-sm text-fg-primary shadow-lg"
          >
            <RadixToast.Description>{t.message}</RadixToast.Description>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport
          data-testid="toast-viewport"
          className="fixed right-4 top-4 z-50 flex w-80 max-w-[100vw] flex-col gap-2 outline-none"
        />
      </RadixToast.Provider>
    </ToastCtx.Provider>
  );
}

const NOOP_TOAST: ToastContextShape = { show: () => undefined };

export function useToast(): ToastContextShape {
  const ctx = useContext(ToastCtx);
  return ctx ?? NOOP_TOAST;
}
