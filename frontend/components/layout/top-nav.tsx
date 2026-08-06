"use client";

import { useRouter } from "next/navigation";
import { Bell, ChevronDown, LogOut, Moon, Search, Settings, Sun } from "lucide-react";
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

export function TopNav() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-20 flex h-[72px] items-center gap-4 border-b border-border bg-background/80 px-6 backdrop-blur-md lg:px-8">
      <MobileNav />

      {/* Search */}
      <div className="relative max-w-md flex-1">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="Search anything..."
          className="h-11 w-full rounded-input border border-border bg-card pl-11 pr-16 text-[15px] text-text-primary placeholder:text-text-muted focus:border-wine focus:outline-none focus:ring-2 focus:ring-wine/15"
        />
        <kbd className="absolute right-3 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded-md border border-border bg-hover px-1.5 py-0.5 text-[11px] font-medium text-text-muted sm:flex">
          ⌘ K
        </kbd>
      </div>

      <div className="flex-1" />

      {/* Notifications */}
      <button className="relative flex h-10 w-10 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-hover">
        <Bell size={18} />
      </button>

      {/* Theme switch */}
      <button
        onClick={toggle}
        aria-label="Toggle theme"
        className="flex h-10 w-10 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-hover"
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 rounded-full p-1 pr-2 outline-none transition-colors hover:bg-hover">
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
