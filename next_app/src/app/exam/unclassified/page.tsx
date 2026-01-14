import { UnclassifiedQueue } from "@/components/exam/UnclassifiedQueue";

export default function UnclassifiedPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Unclassified queue
        </p>
        <h2 className="text-2xl font-semibold text-foreground">
          Review and classify questions
        </h2>
      </div>
      <UnclassifiedQueue />
    </div>
  );
}
