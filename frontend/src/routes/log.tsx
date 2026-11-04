import { createFileRoute } from "@tanstack/react-router";

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

/** The Log tab: the full project log. The shared header and tab bar come from __root.tsx. */
function LogPage() {
  return <ProjectLog />;
}
