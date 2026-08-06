"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Crown, MoreVertical } from "lucide-react";
import { NAV_ITEMS } from "./nav-config";
import { Logo } from "./logo";
import { useAuth } from "@/providers/auth-provider";
import { cn, displayName, initials } from "@/lib/utils";

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[280px] flex-col border-r border-border bg-sidebar lg:flex">
      <div className="flex h-[72px] items-center px-6">
        <Logo />
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex h-12 items-center gap-3 rounded-xl px-4 text-[15px] font-medium transition-colors duration-[180ms]",
                active
                  ? "bg-wine-tint text-wine"
                  : "text-text-secondary hover:bg-hover hover:text-text-primary",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-wine" />
              )}
              <Icon size={18} strokeWidth={2} className={active ? "text-wine" : ""} />
              <span className="flex-1">{item.label}</span>
              {item.comingSoon && (
                <span className="rounded-badge bg-hover px-2 py-0.5 text-[10px] font-medium text-text-muted">
                  Soon
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-4 px-4 pb-4 pt-2">
        {/* Plan card — name reflects the user's real subscription tier. */}
        <div className="rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <Crown size={16} className="text-wine" />
            <span className="text-sm font-semibold capitalize text-text-primary">
              {user?.subscription_tier ?? "free"} Plan
            </span>
          </div>
          <Link
            href="/settings"
            className="mt-3 flex h-9 w-full items-center justify-center rounded-btn border border-border text-sm font-medium text-text-primary transition-colors hover:bg-hover"
          >
            Manage Plan
          </Link>
        </div>

        {/* User row */}
        <div className="flex items-center gap-3 rounded-2xl px-2 py-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-wine text-[13px] font-semibold text-white">
            {initials(user?.name, user?.email)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-text-primary">
              {displayName(user?.name, user?.email)}
            </p>
            <p className="truncate text-[12px] text-text-muted">{user?.email ?? ""}</p>
          </div>
          <MoreVertical size={16} className="text-text-muted" />
        </div>
      </div>
    </aside>
  );
}
