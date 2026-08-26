"use client";

import * as React from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  /** Shown, muted, while `value` is "" and no option carries that value. */
  placeholder?: string;
  disabled?: boolean;
  /** Lands on the trigger, so size overrides such as `h-9 w-[142px]` still work. */
  className?: string;
  id?: string;
  "aria-label"?: string;
}

/**
 * A select whose popup the app draws itself.
 *
 * This used to be a native `<select>`: the closed control was themed but the
 * open list was rendered by the OS, so it ignored the wine palette entirely and
 * came up white in dark mode. Built on the dropdown-menu primitive already in
 * the bundle rather than a second Radix package, and styled to match
 * `components/ui/dropdown-menu.tsx` so every menu in the app reads as one.
 */
export function Select({
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  className,
  id,
  "aria-label": ariaLabel,
}: SelectProps) {
  const selected = options.find((option) => option.value === value);

  return (
    <DropdownMenuPrimitive.Root>
      <div className="relative">
        <DropdownMenuPrimitive.Trigger
          id={id}
          type="button"
          disabled={disabled}
          aria-label={ariaLabel}
          className={cn(
            "flex h-11 w-full items-center rounded-input border border-border bg-card px-3.5 pr-10 text-left text-[15px] text-text-primary",
            "focus:border-wine focus:outline-none focus:ring-2 focus:ring-wine/15 disabled:opacity-50",
            "data-[state=open]:border-wine data-[state=open]:ring-2 data-[state=open]:ring-wine/15",
            className,
          )}
        >
          <span className={cn("truncate", selected ? "" : "text-text-muted")}>
            {selected ? selected.label : placeholder ?? ""}
          </span>
        </DropdownMenuPrimitive.Trigger>
        <ChevronDown
          size={18}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted"
        />
      </div>

      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          sideOffset={6}
          align="start"
          collisionPadding={8}
          className={cn(
            "z-50 w-[var(--radix-dropdown-menu-trigger-width)] min-w-[180px] rounded-2xl border border-border bg-card p-1.5 shadow-card-hover",
            "max-h-[min(320px,var(--radix-dropdown-menu-content-available-height))] overflow-y-auto",
          )}
        >
          <DropdownMenuPrimitive.RadioGroup value={value} onValueChange={onValueChange}>
            {options.map((option) => {
              const active = option.value === value;
              return (
                <DropdownMenuPrimitive.RadioItem
                  key={option.value}
                  value={option.value}
                  disabled={option.disabled}
                  className={cn(
                    "flex cursor-pointer select-none items-center justify-between gap-2.5 rounded-lg px-3 py-2 text-sm outline-none transition-colors",
                    "focus:bg-hover data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
                    active ? "bg-wine-tint text-wine-fg" : "text-text-primary",
                  )}
                >
                  <span className="truncate">{option.label}</span>
                  {active && <Check size={16} className="shrink-0" />}
                </DropdownMenuPrimitive.RadioItem>
              );
            })}
          </DropdownMenuPrimitive.RadioGroup>
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  );
}
