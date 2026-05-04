import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-md border border-border-default bg-bg-elevated p-4 text-fg-primary",
        className,
      )}
      {...props}
    />
  );
}
