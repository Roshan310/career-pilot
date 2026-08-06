import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal table primitives per FRONTEND.md §15: 14px/600 headers, 56px rows,
 * hover #FAFAFA, only horizontal separators (no vertical borders).
 */
function Table({ className, ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full border-collapse text-left", className)} {...props} />
    </div>
  );
}

function THead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("", className)} {...props} />;
}

function TBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} className={className} />;
}

function TR({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("border-b border-divider transition-colors last:border-0", className)}
      {...props}
    />
  );
}

function TH({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn("h-11 px-4 text-sm font-semibold text-text-secondary", className)}
      {...props}
    />
  );
}

function TD({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("h-14 px-4 text-[15px] text-text-primary align-middle", className)} {...props} />;
}

export { Table, THead, TBody, TR, TH, TD };
