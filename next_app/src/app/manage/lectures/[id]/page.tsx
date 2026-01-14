import { getLecture } from "@/lib/api/manage";
import { LectureForm } from "@/components/manage/LectureForm";
import { Card, CardContent } from "@/components/ui/card";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function ManageLectureDetailPage({ params }: PageProps) {
  try {
    const { id } = await params;
    const lecture = await getLecture(id);
    return (
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            Lecture
          </p>
          <h2 className="text-2xl font-semibold text-foreground">Edit lecture</h2>
        </div>
        <LectureForm blockId={lecture.blockId} initial={lecture} />
      </div>
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load lecture.";
    return (
      <Card className="border border-danger/30 bg-danger/10">
        <CardContent className="space-y-2 p-6">
          <p className="text-lg font-semibold text-foreground">Lecture unavailable</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </CardContent>
      </Card>
    );
  }
}
