import { PROJECT_LOG, REPOSITORY_URL } from "@/lib/projectLog";

/** Formats a YYYY-MM-DD date, read as UTC so it can't shift a day in another time zone. */
function formatDate(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** What has changed and why, including tests that didn't improve the model. */
export function ProjectLog() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-sm font-medium">Project log</h2>
        <p className="text-muted-foreground text-sm">
          How the model is being adjusted and re-evaluated, including what didn&apos;t work. The
          code and prediction history are{" "}
          <a href={REPOSITORY_URL} className="underline underline-offset-2 hover:text-foreground">
            public on GitHub
          </a>
          .
        </p>
      </div>
      <ol className="space-y-4">
        {PROJECT_LOG.map((entry) => (
          <li key={`${entry.date}-${entry.title}`} className="border-l-2 pl-4">
            <p className="text-muted-foreground text-xs">{formatDate(entry.date)}</p>
            <h3 className="text-sm font-medium">{entry.title}</h3>
            <p className="text-muted-foreground mt-1 text-sm">{entry.why}</p>
            <p className="mt-1 text-sm">{entry.result}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
