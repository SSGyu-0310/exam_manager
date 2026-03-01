type ChoiceLike = {
  number?: number | null;
  choiceNumber?: number | null;
  content?: string | null;
};

const INTEGRATED_CHOICE_HEADER = "[기존 객관식 선지]";

const resolveChoiceNumber = (choice: ChoiceLike, index: number) =>
  typeof choice.number === "number"
    ? choice.number
    : typeof choice.choiceNumber === "number"
      ? choice.choiceNumber
      : index + 1;

export const mergeChoicesIntoStem = (
  stem: string | null | undefined,
  choices: ChoiceLike[]
) => {
  const lines = choices
    .map((choice, index) => ({
      number: resolveChoiceNumber(choice, index),
      content: (choice.content ?? "").trim(),
    }))
    .filter((choice) => choice.content.length > 0)
    .map((choice) => `${choice.number}. ${choice.content}`);

  const base = (stem ?? "").trimEnd();
  if (lines.length === 0) {
    return base;
  }

  const block = `${INTEGRATED_CHOICE_HEADER}\n${lines.join("\n")}`;
  if (base.includes(INTEGRATED_CHOICE_HEADER)) {
    return base;
  }
  return base ? `${base}\n\n${block}` : block;
};

