"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

// Goes back in history when there is one (a deep link opened in a fresh tab has none), and
// otherwise to the given parent route.
export function BackButton({
  fallbackHref,
  label = "Back",
}: {
  fallbackHref: string;
  label?: string;
}) {
  const router = useRouter();
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 self-start"
      onClick={() => {
        if (window.history.length > 1) router.back();
        else router.push(fallbackHref);
      }}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      {label}
    </Button>
  );
}
