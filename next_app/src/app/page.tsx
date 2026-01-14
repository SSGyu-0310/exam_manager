export default function Home() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="rounded-2xl border border-border/70 bg-card p-8 shadow-soft">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Exam Manager</p>
        <h2 className="mt-3 text-3xl font-semibold leading-tight text-foreground">
          Built for rapid lecture curation and exam delivery.
        </h2>
        <p className="mt-4 text-sm text-muted-foreground">
          Move through blocks, lectures, exams, and unclassified queues with a single
          navigation spine. This shell will host the new Next.js admin flows.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-soft"
            href="/manage"
          >
            Go to Dashboard
          </a>
          <a
            className="inline-flex h-11 items-center justify-center rounded-md border border-border bg-card px-5 text-sm font-semibold text-foreground"
            href="/lectures"
          >
            Practice Library
          </a>
        </div>
      </div>
      <div className="rounded-2xl border border-border/70 bg-muted/70 p-6 text-sm text-muted-foreground shadow-soft">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Migration Status
        </p>
        <ul className="mt-4 space-y-3">
          <li className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 rounded-full bg-success" />
            App shell, tokens, and core UI components are in place.
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 rounded-full bg-warning" />
            Read-only admin screens are next (blocks, lectures, exams).
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 rounded-full bg-danger" />
            CRUD, PDF upload, and AI flows will follow in Phase 3+.
          </li>
        </ul>
      </div>
    </div>
  );
}
