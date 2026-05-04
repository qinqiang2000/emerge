import * as RadixSelect from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Select({
  value,
  onValueChange,
  placeholder,
  children,
  className,
  disabled,
}: {
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <RadixSelect.Trigger
        className={cn(
          "inline-flex items-center justify-between gap-2 rounded-md border border-border-default bg-bg-surface px-3 py-1.5 text-sm text-fg-primary disabled:opacity-50",
          className,
        )}
      >
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon>
          <ChevronDown size={16} />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className="z-50 overflow-hidden rounded-md border border-border-default bg-bg-elevated text-fg-primary shadow-lg"
        >
          <RadixSelect.Viewport className="p-1">{children}</RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}

export function SelectItem({
  value,
  children,
}: {
  value: string;
  children: ReactNode;
}) {
  return (
    <RadixSelect.Item
      value={value}
      className="relative flex cursor-default select-none items-center rounded px-6 py-1.5 text-sm text-fg-primary outline-none data-[highlighted]:bg-bg-muted"
    >
      <RadixSelect.ItemText>{children}</RadixSelect.ItemText>
      <RadixSelect.ItemIndicator className="absolute left-1.5">
        <Check size={14} />
      </RadixSelect.ItemIndicator>
    </RadixSelect.Item>
  );
}
