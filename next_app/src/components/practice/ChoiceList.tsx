import { cn } from "@/lib/utils";
import { resolveImageUrl } from "@/lib/image";

import type { PracticeChoice } from "@/components/practice/types";

type ChoiceListProps = {
  choices: PracticeChoice[];
  multiple?: boolean;
  selected: number[];
  onChange: (next: number[]) => void;
};

const getChoiceId = (choice: PracticeChoice, index: number) =>
  typeof choice.number === "number" ? choice.number : index + 1;

export function ChoiceList({ choices, multiple, selected, onChange }: ChoiceListProps) {
  return (
    <div className="space-y-3">
      {choices.map((choice, index) => {
        const choiceId = getChoiceId(choice, index);
        const checked = selected.includes(choiceId);
        const label = choice.content ?? `Choice ${choiceId}`;
        const image = resolveImageUrl(choice.imageUrl ?? choice.image);

        const toggle = () => {
          if (multiple) {
            const next = checked
              ? selected.filter((value) => value !== choiceId)
              : [...selected, choiceId];
            onChange(next);
          } else {
            onChange([choiceId]);
          }
        };

        return (
          <label
            key={choiceId}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 text-sm transition",
              checked
                ? "border-primary bg-primary text-primary-foreground shadow-soft"
                : "border-border/70 bg-card text-foreground hover:border-border/80"
            )}
          >
            <input
              type={multiple ? "checkbox" : "radio"}
              name="practice-choice"
              checked={checked}
              onChange={toggle}
              className="mt-[3px] h-4 w-4 shrink-0 accent-primary"
            />
            <div className={cn(
              "text-sm font-semibold shrink-0",
              checked ? "text-primary-foreground/70" : "text-muted-foreground"
            )}>
              {choiceId}
            </div>
            <div className="flex-1 space-y-2">
              <p className="text-sm leading-relaxed">{label}</p>
              {typeof image === "string" && image.length > 0 && (
                <img
                  src={image}
                  alt={`Choice ${choiceId}`}
                  className="max-h-48 rounded-lg border border-border/60 object-contain"
                />
              )}
            </div>
          </label>
        );
      })}
    </div>
  );
}
