import * as RadixSwitch from "@radix-ui/react-switch";
import { type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

export function Switch({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof RadixSwitch.Root>) {
  return (
    <RadixSwitch.Root
      {...props}
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border-default bg-bg-muted transition-colors data-[state=checked]:bg-accent-primary",
        className,
      )}
    >
      <RadixSwitch.Thumb className="pointer-events-none block h-4 w-4 translate-x-0.5 rounded-full bg-bg-surface shadow transition-transform data-[state=checked]:translate-x-4" />
    </RadixSwitch.Root>
  );
}
