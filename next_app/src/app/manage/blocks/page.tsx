import { getBlocks } from "@/lib/api/manage";
import Link from "next/link";

import { BlocksTable } from "@/components/manage/BlocksTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default async function ManageBlocksPage() {
  try {
    const blocks = await getBlocks();
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              Blocks
            </p>
            <h2 className="text-2xl font-semibold text-foreground">Block library</h2>
          </div>
          <Button asChild>
            <Link href="/manage/blocks/new">New block</Link>
          </Button>
        </div>
        <BlocksTable blocks={blocks} showActions />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load blocks.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Blocks unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
