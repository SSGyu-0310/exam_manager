import { BookMarked } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import { Card, CardContent } from "@/components/ui/card";

export function LectureEmptyState() {
  const { t } = useLanguage();

  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="rounded-full bg-secondary p-3 text-secondary-foreground">
          < BookMarked className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <p className="text-base font-semibold text-foreground">{t("learn.noLectures")}</p>
          <p className="text-sm text-muted-foreground">
            {t("learn.noLecturesDesc")}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

