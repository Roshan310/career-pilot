"use client";

import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, Moon, Settings, Sun } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { useTheme } from "@/providers/theme-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { displayName, initials } from "@/lib/utils";
import { MobileNav } from "./mobile-nav";

/**
 * Deliberately sparse. A global search field and a notifications bell used to
 * sit here; neither had a handler behind it and the search advertised a ⌘K
 * shortcut that was never bound. Prominent controls that do nothing read as a
 * half-built product, so they are gone until there is something to wire them to.
 */
export function TopNav() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-20 flex h-[72px] items-center gap-2 border-b border-border bg-background/80 px-6 backdrop-blur-md lg:px-8">
      <MobileNav />

      <div className="flex-1" />

      <button
        onClick={toggle}
        aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        className="flex h-10 w-10 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Account menu"
          className="flex items-center gap-2 rounded-full p-1 pr-2 outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-wine/40"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-wine text-[13px] font-semibold text-white">
            {initials(user?.name, user?.email)}
          </div>
          <ChevronDown size={16} className="text-text-muted" />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>
            <p className="text-sm font-semibold text-text-primary">
              {displayName(user?.name, user?.email)}
            </p>
            <p className="truncate text-[12px] text-text-muted">{user?.email ?? ""}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => router.push("/settings")}>
            <Settings size={16} />
            Settings
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={logout} className="text-error focus:bg-error-bg">
            <LogOut size={16} />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
