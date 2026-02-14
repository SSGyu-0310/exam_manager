import { notFound } from "next/navigation";

import { AiClassificationPreview } from "@/components/exam/AiClassificationPreview";

type PageProps = {
  params: Promise<{ jobId: string }>;
};

export default async function ClassificationPreviewPage({ params }: PageProps) {
  const { jobId } = await params;
  const parsedJobId = Number(jobId);
  if (!Number.isInteger(parsedJobId) || parsedJobId <= 0) {
    notFound();
  }

  return <AiClassificationPreview jobId={parsedJobId} />;
}
