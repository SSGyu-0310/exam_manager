"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useLanguage } from "@/context/LanguageContext";

export type ShortcutItem = {
  keys: string;
  description: string;
};

export type ShortcutSection = {
  title: string;
  items: ShortcutItem[];
};

type ShortcutHelpDialogProps = {
  open: boolean;
  title: string;
  description: string;
  sections: ShortcutSection[];
  onClose: () => void;
};

export function ShortcutHelpDialog({
  open,
  title,
  description,
  sections,
  onClose,
}: ShortcutHelpDialogProps) {
  const { t } = useLanguage();

  useEffect(() => {
    if (!open) return;
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <Card
        className="w-full max-w-2xl border border-border/80 bg-card/95 shadow-float backdrop-blur"
        onClick={(event) => event.stopPropagation()}
      >
        <CardHeader className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-lg">{title}</CardTitle>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close shortcut help">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {sections.map((section) => (
            <div key={section.title} className="space-y-2 rounded-xl border border-border/70 bg-muted/40 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {section.title}
              </p>
              <div className="space-y-2">
                {section.items.map((item) => (
                  <div key={`${section.title}-${item.keys}`} className="flex items-start justify-between gap-4 text-sm">
                    <span className="font-mono text-foreground">{item.keys}</span>
                    <span className="text-right text-muted-foreground">{item.description}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            {t("practiceSession.shortcuts.helpFooter")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
