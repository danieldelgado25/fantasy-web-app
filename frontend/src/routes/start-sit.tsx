import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PlayerSearch } from "@/components/PlayerSearch";
import { StartSitCompare } from "@/components/StartSitCompare";
import { fetchProjections, type Player } from "@/lib/api";

export const Route = createFileRoute("/start-sit")({
  head: () => ({
    meta: [
      { title: "Start/Sit · WR Projection Tool" },
      {
        name: "description",
        content: "Compare two wide receivers' projections and matchups to decide who to start.",
      },
    ],
  }),
  component: StartSitPage,
});

/** The Start/Sit tab: pick two WRs and compare their projections and matchups. */
function StartSitPage() {
  // The two picks, empty until chosen.
  const [first, setFirst] = useState<Player | null>(null);
  const [second, setSecond] = useState<Player | null>(null);

  // Same query key as the other tabs, so switching tabs reuses the cached file.
  const projectionsQuery = useQuery({ queryKey: ["projections"], queryFn: fetchProjections });
  const players = projectionsQuery.data?.players ?? [];

  /** Full projection for a pick, or null if not picked or missing from the file. */
  const projectionFor = (pick: Player | null) =>
    players.find((p) => p.player_id === pick?.player_id) ?? null;
  const a = projectionFor(first);
  const b = projectionFor(second);

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground text-sm">
        Pick two receivers to compare their projected PPR points and this week's matchups.
      </p>

      {/* Stacked on phones, side by side from small screens up. */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Wrapping label names each picker for screen readers. */}
        <label className="space-y-2 text-sm font-medium">
          <span>First player</span>
          <PlayerSearch
            players={players}
            selectedPlayer={first}
            onSelect={setFirst}
            disabled={projectionsQuery.isLoading}
          />
        </label>
        <label className="space-y-2 text-sm font-medium">
          <span>Second player</span>
          <PlayerSearch
            players={players}
            selectedPlayer={second}
            onSelect={setSecond}
            disabled={projectionsQuery.isLoading}
          />
        </label>
      </div>

      {projectionsQuery.error && (
        <p className="text-destructive text-sm">Projections couldn't be loaded.</p>
      )}
      {a && b && a.player_id === b.player_id && (
        <p className="text-muted-foreground text-sm">Pick two different players to compare.</p>
      )}
      {a && b && a.player_id !== b.player_id && <StartSitCompare a={a} b={b} />}
    </div>
  );
}
