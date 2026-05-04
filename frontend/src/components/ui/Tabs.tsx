import * as RadixTabs from "@radix-ui/react-tabs";
import { type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Tabs({
  value,
  onValueChange,
  defaultValue,
  children,
  className,
}: {
  value?: string;
  onValueChange?: (value: string) => void;
  defaultValue?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Root
      value={value}
      onValueChange={onValueChange}
      defaultValue={defaultValue}
      className={className}
    >
      {children}
    </RadixTabs.Root>
  );
}

export function TabsList({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.List
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border-default bg-bg-elevated p-1",
        className,
      )}
    >
      {children}
    </RadixTabs.List>
  );
}

export function TabsTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Trigger
      value={value}
      className={cn(
        "rounded-sm px-3 py-1 text-sm text-fg-muted data-[state=active]:bg-bg-surface data-[state=active]:text-fg-primary",
        className,
      )}
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Content value={value} className={className}>
      {children}
    </RadixTabs.Content>
  );
}
