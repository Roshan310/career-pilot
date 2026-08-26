"use client";

import { AccountMenu } from "./account-menu";
import { MobileNav } from "./mobile-nav";

/**
 * Mobile only. The sidebar carries the logo, navigation and account menu on
 * `lg` and up, so above that width there is no chrome over the content at all;
 * below it the sidebar is hidden and this bar holds the drawer trigger.
 *
 * Deliberately sparse. A global search field and a notifications bell used to
 * sit here; neither had a handler behind it and the search advertised a ⌘K
 * shortcut that was never bound. Prominent controls that do nothing read as a
 * half-built product, so they are gone until there is something to wire them to.
 */
export function MobileBar() {
  return (
    <header className="sticky top-0 z-20 flex h-[72px] items-center gap-2 border-b border-border bg-background/80 px-6 backdrop-blur-md lg:hidden">
      <MobileNav />
      <div className="flex-1" />
      <AccountMenu variant="compact" />
    </header>
  );
}
