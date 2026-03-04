import Link from "next/link";
import { Search } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { LectureSort } from "@/components/lectures/types";

type LectureHeaderProps = {
  query: string;
  onQueryChange: (value: string) => void;
  sort: LectureSort;
  onSortChange: (value: LectureSort) => void;
  totalCount: number;
  filteredCount: number;
  quickStartHref?: string | null;
  quickStartLabel?: string | null;
};

export function LectureHeader({
  query,
  onQueryChange,
  sort,
  onSortChange,
  totalCount,
  filteredCount,
  quickStartHref,
  quickStartLabel,
}: LectureHeaderProps) {
  const { t } = useLanguage();
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            {t("learn.studyLibrary")}
          </p>
          <h1 className="text-2xl font-semibold text-foreground">{t("learn.lectures")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("learn.readyToStudy")
              .replace("{filtered}", String(filteredCount))
              .replace("{total}", String(totalCount))}
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:flex-row xl:w-auto">
          <div className="relative w-full xl:w-[360px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder={t("learn.searchLectures")}
              className="h-11 pl-10"
            />
          </div>
          <div className="w-full sm:w-44">
            <Select
              value={sort}
              onChange={(event) => onSortChange(event.target.value as LectureSort)}
              aria-label={t("learn.searchLectures")}
              className="h-11"
            >
              <option value="manual">{t("learn.sortByManageOrder")}</option>
              <option value="title">{t("learn.sortByTitle")}</option>
              <option value="questions">{t("learn.sortByQuestions")}</option>
              <option value="recent">{t("learn.sortByRecentStudy")}</option>
            </Select>
          </div>
          {quickStartHref && quickStartLabel && (
            <Button asChild className="h-11 whitespace-nowrap px-4">
              <Link href={quickStartHref}>{quickStartLabel}</Link>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
