"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

type QuestionDetailHotkeysProps = {
  prevHref?: string | null;
  nextHref?: string | null;
};

export function QuestionDetailHotkeys({ prevHref, nextHref }: QuestionDetailHotkeysProps) {
  const router = useRouter();

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;

      const active = document.activeElement as HTMLElement | null;
      if (active) {
        const tag = active.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (active.isContentEditable) return;
      }

      if (event.key === "ArrowLeft" && prevHref) {
        event.preventDefault();
        router.push(prevHref);
      }

      if (event.key === "ArrowRight" && nextHref) {
        event.preventDefault();
        router.push(nextHref);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nextHref, prevHref, router]);

  return null;
}
