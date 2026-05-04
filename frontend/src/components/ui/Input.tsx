import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "block w-full rounded-md border border-border-default bg-bg-surface px-3 py-1.5 text-sm text-fg-primary placeholder:text-fg-muted focus:border-accent-primary focus:outline-none",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
