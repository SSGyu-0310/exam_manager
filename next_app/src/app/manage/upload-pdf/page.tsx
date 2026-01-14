import { UploadPdfForm } from "@/components/manage/UploadPdfForm";

export default function ManageUploadPdfPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          PDF upload
        </p>
        <h2 className="text-2xl font-semibold text-foreground">Create an exam from PDF</h2>
      </div>
      <UploadPdfForm />
    </div>
  );
}
