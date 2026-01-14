import { getBlock } from "@/lib/api/manage";
import { BlockForm } from "@/components/manage/BlockForm";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ManageBlockEditPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const block = await getBlock(id);
    return (
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Blocks
          </p>
          <h2 className="text-2xl font-semibold text-foreground">Edit block</h2>
        </div>
        <BlockForm initial={block} />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load block.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Block unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
