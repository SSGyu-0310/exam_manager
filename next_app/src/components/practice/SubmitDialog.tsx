import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/LanguageContext";

type SubmitDialogProps = {
  open: boolean;
  unansweredCount: number;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
};

export function SubmitDialog({
  open,
  unansweredCount,
  onClose,
  onConfirm,
  loading,
}: SubmitDialogProps) {
  const { t } = useLanguage();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md border border-border/70 bg-card/95 shadow-float backdrop-blur">
        <CardHeader className="space-y-2">
          <CardTitle className="text-lg">{t("practiceSession.submitDialog.title")}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("practiceSession.submitDialog.unansweredCount").replace("{count}", String(unansweredCount))}
          </p>
        </CardHeader>
        <CardContent className="flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            {t("practiceSession.submitDialog.cancel")}
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                {t("practiceSession.submitDialog.submitting")}
              </>
            ) : (
              t("practiceSession.submitDialog.submit")
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
