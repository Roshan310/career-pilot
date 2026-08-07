"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { NAV_ITEMS, isActive } from "./nav-config";
import { Logo } from "./logo";
import { cn } from "@/lib/utils";

/**
 * Radix Dialog rather than a hand-rolled overlay: the previous version had no
 * role, no focus trap, no Escape handler and no scroll lock, so opening the menu
 * on a phone left the page scrolling underneath and stranded keyboard focus.
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="lg:hidden">
      <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
        <DialogPrimitive.Trigger
          aria-label="Open menu"
          className="flex h-10 w-10 items-center justify-center rounded-full text-text-secondary hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
        >
          <Menu size={20} />
        </DialogPrimitive.Trigger>

        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
          <DialogPrimitive.Content
            className="fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-border bg-sidebar p-4 shadow-modal focus:outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-left"
          >
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <div className="mb-4 flex h-12 items-center justify-between px-2">
              <Logo />
              <DialogPrimitive.Close
                aria-label="Close menu"
                className="flex h-8 w-8 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
              >
                <X size={20} />
              </DialogPrimitive.Close>
            </div>
            <nav className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-12 items-center gap-3 rounded-xl px-4 text-[15px] font-medium",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40",
                      active ? "bg-wine-tint text-wine-fg" : "text-text-secondary hover:bg-hover",
                    )}
                  >
                    <Icon size={18} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </div>
  );
}
