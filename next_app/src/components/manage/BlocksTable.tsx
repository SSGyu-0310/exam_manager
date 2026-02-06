import Link from "next/link";

import type { ManageBlock } from "@/lib/api/manage";
import { Badge } from "@/components/ui/badge";
import { TableRow } from "@/components/ui/table-row";

type BlocksTableProps = {
  blocks: ManageBlock[];
  showActions?: boolean;
};

export function BlocksTable({ blocks, showActions = false }: BlocksTableProps) {
  if (!blocks.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/70 p-6 text-sm text-muted-foreground">
        No blocks found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/80">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.2em] text-muted-foreground">
          <tr>
            <th className="px-5 py-3">Subject</th>
            <th className="px-5 py-3">Block</th>
            <th className="px-5 py-3">Lectures</th>
            <th className="px-5 py-3">Questions</th>
            <th className="px-5 py-3">Order</th>
            {showActions && <th className="px-5 py-3">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {blocks.map((block) => (
            <TableRow key={block.id}>
              <td className="px-5 py-4 text-muted-foreground">
                {block.subject || "Unassigned"}
              </td>
              <td className="px-5 py-4">
                <Link
                  href={`/manage/blocks/${block.id}/lectures`}
                  className="font-semibold text-foreground hover:underline"
                >
                  {block.name}
                </Link>
                {block.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{block.description}</p>
                )}
              </td>
              <td className="px-5 py-4">
                <Badge variant="neutral">{block.lectureCount ?? 0}</Badge>
              </td>
              <td className="px-5 py-4">
                <Badge variant="neutral">{block.questionCount ?? 0}</Badge>
              </td>
              <td className="px-5 py-4 text-muted-foreground">{block.order ?? 0}</td>
              {showActions && (
                <td className="px-5 py-4">
                  <Link
                    href={`/manage/blocks/${block.id}/edit`}
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-foreground/80 hover:underline"
                  >
                    Edit
                  </Link>
                </td>
              )}
            </TableRow>
          ))}
        </tbody>
      </table>
    </div>
  );
}
