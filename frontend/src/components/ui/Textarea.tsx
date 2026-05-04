import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "block w-full rounded-md border border-border-default bg-bg-surface px-3 py-2 text-sm text-fg-primary placeholder:text-fg-muted focus:border-accent-primary focus:outline-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
