import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Tone = "default" | "muted" | "success" | "warning" | "error" | "accent";

const TONE: Record<Tone, string> = {
  default: "border-border-default bg-bg-elevated text-fg-primary",
  muted: "border-border-default bg-bg-muted text-fg-muted",
  success: "border-status-success bg-bg-elevated text-status-success",
  warning: "border-status-warning bg-bg-elevated text-status-warning",
  error: "border-status-error bg-bg-elevated text-status-error",
  accent: "border-accent-primary bg-bg-elevated text-accent-primary",
};

export function Badge({
  tone = "default",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium",
        TONE[tone],
        className,
      )}
      {...props}
    />
  );
}
