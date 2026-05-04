import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

const VARIANT: Record<Variant, string> = {
  primary: "bg-accent-primary text-accent-primary-fg hover:opacity-90",
  secondary:
    "bg-bg-elevated text-fg-primary border border-border-default hover:bg-bg-muted",
  ghost: "text-fg-primary hover:bg-bg-muted",
  danger: "bg-status-error text-fg-inverse hover:opacity-90",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-opacity disabled:opacity-50",
        size === "sm" ? "px-2 py-1 text-sm" : "px-3 py-1.5 text-sm",
        VARIANT[variant],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
