import { createFileRoute, Link } from "@tanstack/react-router";

import { ProjectLog } from "@/components/ProjectLog";

export const Route = createFileRoute("/log")({
  head: () => ({
    meta: [
      { title: "Project Log · WR Projection Tool" },
      {
        name: "description",
        content: "How the WR projection model is being adjusted and re-evaluated.",
      },
    ],
  }),
  component: LogPage,
});

/** The full project log on its own page, so the main page stays focused on projections. */
function LogPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Same header accent as the main page. */}
      <header className="border-b-[3px] border-primary bg-card px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <Link to="/" className="text-muted-foreground text-sm hover:text-foreground">
            ← Back to projections
          </Link>
        </div>
      </header>
      <main className="flex-1 px-4 py-8">
        <div className="mx-auto max-w-2xl">
          <ProjectLog />
        </div>
      </main>
    </div>
  );
}
