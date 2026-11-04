import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { AccuracyPanel } from "@/components/AccuracyPanel";
import { HowItWorks } from "@/components/HowItWorks";
import { Button } from "@/components/ui/button";
import { fetchAccuracy } from "@/lib/api";
import { REPOSITORY_URL } from "@/lib/projectLog";

export const Route = createFileRoute("/accuracy")({
  head: () => ({
    meta: [
      { title: "Accuracy · WR Projection Tool" },
      {
        name: "description",
        content: "How accurate the WR projections have been, and how the model makes them.",
      },
    ],
  }),
  component: AccuracyPage,
});

/** The Accuracy tab: the model's scored results, then how it works, for technical readers. */
function AccuracyPage() {
  // Same query key as the Projections tab, so switching tabs reuses the cached file.
  const accuracyQuery = useQuery({ queryKey: ["accuracy"], queryFn: fetchAccuracy });

  return (
    <div className="space-y-6">
      {accuracyQuery.isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {accuracyQuery.error && (
        <p className="text-destructive text-sm">Accuracy results couldn't be loaded.</p>
      )}
      {accuracyQuery.data && <AccuracyPanel accuracy={accuracyQuery.data} />}

      <HowItWorks />

      {/* The code sits next to the explanation of how the model works. */}
      <Button asChild variant="outline" size="sm">
        <a href={REPOSITORY_URL}>Source code on GitHub</a>
      </Button>
    </div>
  );
}
