import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PlayerSearch } from "@/components/PlayerSearch";
import { ProjectionPanel } from "@/components/ProjectionPanel";
import { fetchProjections, type Player } from "@/lib/api";

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

  const projectionsQuery = useQuery({
    queryKey: ["projections"],
    queryFn: fetchProjections,
  });

  const players = projectionsQuery.data?.players ?? [];
  const selectedProjection =
    players.find((p) => p.player_id === selectedPlayer?.player_id) ?? null;

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
              players={players}
              selectedPlayer={selectedPlayer}
              onSelect={setSelectedPlayer}
              disabled={projectionsQuery.isLoading}
            />
          </div>

          <ProjectionPanel
            projection={selectedProjection}
            isLoading={projectionsQuery.isLoading}
            error={projectionsQuery.error as Error | null}
          />
        </div>
      </main>
    </div>
  );
}
