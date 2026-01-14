import * as React from "react";

import { cn } from "@/lib/utils";

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        "border-b border-border/60 transition-colors hover:bg-muted/70 focus-within:bg-muted/50 data-[state=selected]:bg-accent/70",
        className
      )}
      {...props}
    />
  )
);
TableRow.displayName = "TableRow";

export { TableRow };
