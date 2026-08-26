"use client";

import { useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, LogOut, Moon, Settings, Sun } from "lucide-react";
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

/**
 * The single account menu. The sidebar and the mobile bar both render this so
 * the two avatars can never drift into offering different actions — the theme
 * toggle in particular used to be a separate button that only existed in the
 * top bar, which left it unreachable once that bar was removed.
 */
export function AccountMenu({ variant }: { variant: "sidebar" | "compact" }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const router = useRouter();

  const name = displayName(user?.name, user?.email);
  const dark = theme === "dark";

  return (
    <DropdownMenu>
      {variant === "sidebar" ? (
        <DropdownMenuTrigger
          type="button"
          aria-label="Account menu"
          className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-wine/40"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-wine text-[13px] font-semibold text-white">
            {initials(user?.name, user?.email)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-text-primary">{name}</p>
            <p className="truncate text-[12px] text-text-muted">{user?.email ?? ""}</p>
          </div>
          <ChevronUp size={16} className="shrink-0 text-text-muted" />
        </DropdownMenuTrigger>
      ) : (
        <DropdownMenuTrigger
          type="button"
          aria-label="Account menu"
          className="flex items-center gap-2 rounded-full p-1 pr-2 outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-wine/40"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-wine text-[13px] font-semibold text-white">
            {initials(user?.name, user?.email)}
          </div>
          <ChevronDown size={16} className="text-text-muted" />
        </DropdownMenuTrigger>
      )}

      <DropdownMenuContent
        side={variant === "sidebar" ? "top" : "bottom"}
        align={variant === "sidebar" ? "start" : "end"}
      >
        <DropdownMenuLabel>
          <p className="text-sm font-semibold text-text-primary">{name}</p>
          <p className="truncate text-[12px] text-text-muted">{user?.email ?? ""}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          // Keeping the menu open means the palette visibly flips under the
          // cursor; closing it would hide the very thing being changed.
          onSelect={(event) => {
            event.preventDefault();
            toggle();
          }}
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
          {dark ? "Light mode" : "Dark mode"}
        </DropdownMenuItem>
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
  );
}
