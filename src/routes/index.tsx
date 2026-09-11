import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PlayerSearch } from "@/components/PlayerSearch";
import { ProjectionPanel } from "@/components/ProjectionPanel";
import { fetchPlayers, fetchProjection, type Player } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "WR Projection Tool" },
      {
        name: "description",
        content:
          "Single-page fantasy football projection tool for NFL wide receivers.",
      },
      { property: "og:title", content: "WR Projection Tool" },
      {
        property: "og:description",
        content:
          "Single-page fantasy football projection tool for NFL wide receivers.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

function Index() {
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);

  const playersQuery = useQuery({
    queryKey: ["players"],
    queryFn: fetchPlayers,
  });

  const projectionQuery = useQuery({
    queryKey: ["projection", selectedPlayer?.player_id],
    queryFn: () => fetchProjection(selectedPlayer!.player_id),
    enabled: !!selectedPlayer,
  });

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b bg-card px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <h1 className="text-xl font-semibold tracking-tight">
            WR Projection Tool
          </h1>
          <p className="text-muted-foreground text-sm">
            Fantasy football projections for NFL wide receivers
          </p>
        </div>
      </header>

      <main className="flex-1 px-4 py-8">
        <div className="mx-auto max-w-2xl space-y-6">
          <div className="space-y-2">
            <label
              htmlFor="player-search"
              className="text-sm font-medium leading-none"
            >
              Select a player
            </label>
            <PlayerSearch
              players={playersQuery.data ?? []}
              selectedPlayer={selectedPlayer}
              onSelect={setSelectedPlayer}
              disabled={playersQuery.isLoading}
            />
          </div>

          <ProjectionPanel
            projection={projectionQuery.data ?? null}
            isLoading={projectionQuery.isLoading}
            error={projectionQuery.error as Error | null}
          />
        </div>
      </main>
    </div>
  );
}
