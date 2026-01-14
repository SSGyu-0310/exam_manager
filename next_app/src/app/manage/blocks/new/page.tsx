import { BlockForm } from "@/components/manage/BlockForm";

export default function ManageBlockCreatePage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Blocks
        </p>
        <h2 className="text-2xl font-semibold text-foreground">New block</h2>
      </div>
      <BlockForm />
    </div>
  );
}
