import * as React from "react";

import { cn } from "@/lib/utils";

export const Checkbox = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    type="checkbox"
    ref={ref}
    className={cn(
      "border-input text-primary h-5 w-5 cursor-pointer rounded focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed",
      className,
    )}
    {...props}
  />
));
Checkbox.displayName = "Checkbox";
