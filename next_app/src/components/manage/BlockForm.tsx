"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  createBlock,
  deleteBlock,
  updateBlock,
  type ManageBlock,
  type ManageBlockInput,
} from "@/lib/api/manage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type BlockFormProps = {
  initial?: ManageBlock | null;
};

export function BlockForm({ initial }: BlockFormProps) {
  const router = useRouter();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [order, setOrder] = useState(initial?.order ?? 0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    const payload: ManageBlockInput = {
      name: name.trim(),
      description: description?.trim() || null,
      order: Number.isFinite(order) ? Number(order) : 0,
    };
    try {
      if (initial?.id) {
        await updateBlock(initial.id, payload);
        setSuccess("Block updated.");
      } else {
        await createBlock(payload);
        setSuccess("Block created.");
      }
      router.push("/manage/blocks");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save block.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initial?.id) return;
    const confirmed = window.confirm("Delete this block? This cannot be undone.");
    if (!confirmed) return;
    setSaving(true);
    setError(null);
    try {
      await deleteBlock(initial.id);
      router.push("/manage/blocks");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete block.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border border-border/70 bg-card/85 shadow-soft">
      <CardContent className="space-y-6 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Name
            </label>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Order
            </label>
            <Input
              type="number"
              value={order}
              onChange={(event) => setOrder(Number(event.target.value))}
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Description
          </label>
          <Textarea
            value={description ?? ""}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
            {success}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {initial?.id ? (
            <Button variant="outline" onClick={handleDelete} disabled={saving}>
              Delete block
            </Button>
          ) : (
            <div />
          )}
          <Button onClick={handleSubmit} disabled={saving || !name.trim()}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
