import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-overlay/40" />
        <RadixDialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 w-[min(36rem,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-md border border-border-default bg-bg-surface p-6 text-fg-primary shadow-lg",
            className,
          )}
        >
          <div className="mb-3 flex items-center justify-between">
            <RadixDialog.Title className="text-lg font-semibold">
              {title}
            </RadixDialog.Title>
            <RadixDialog.Close className="text-fg-muted hover:text-fg-primary">
              <X size={18} />
            </RadixDialog.Close>
          </div>
          {description ? (
            <RadixDialog.Description className="mb-3 text-xs text-fg-muted">
              {description}
            </RadixDialog.Description>
          ) : null}
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
