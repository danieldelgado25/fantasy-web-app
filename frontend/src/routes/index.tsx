import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AccuracyPanel } from "@/components/AccuracyPanel";
import { PlayerSearch } from "@/components/PlayerSearch";
import { ProjectionPanel } from "@/components/ProjectionPanel";
import { ProjectLog } from "@/components/ProjectLog";
import { TopPlayersTable } from "@/components/TopPlayersTable";
import { fetchAccuracy, fetchProjections, type Player } from "@/lib/api";

/** How many top-ranked players the table lists. Search reaches everyone else. */
const TOP_PLAYERS_SHOWN = 20;

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "WR Projection Tool" },
      {
        name: "description",
        content: "Single-page fantasy football projection tool for NFL wide receivers.",
      },
      { property: "og:title", content: "WR Projection Tool" },
      {
        property: "og:description",
        content: "Single-page fantasy football projection tool for NFL wide receivers.",
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

  const accuracyQuery = useQuery({
    queryKey: ["accuracy"],
    queryFn: fetchAccuracy,
  });

  const generatedAt = projectionsQuery.data?.generated_at;
  const players = projectionsQuery.data?.players ?? [];
  const topPlayers = players.filter((p) => p.rank <= TOP_PLAYERS_SHOWN);
  const selectedProjection = players.find((p) => p.player_id === selectedPlayer?.player_id) ?? null;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b bg-card px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <h1 className="text-xl font-semibold tracking-tight">WR Projection Tool</h1>
          <p className="text-muted-foreground text-sm">
            Fantasy football projections for NFL wide receivers
          </p>
          <p className="text-muted-foreground mt-2 text-xs">
            Estimates from a statistical model trained on past NFL games, not guarantees. Injuries
            and late news may not be reflected.
            {generatedAt && ` Updated ${new Date(generatedAt).toLocaleString()}.`}
          </p>
        </div>
      </header>

      <main className="flex-1 px-4 py-8">
        <div className="mx-auto max-w-2xl space-y-6">
          <div className="space-y-2">
            <label htmlFor="player-search" className="text-sm font-medium leading-none">
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

          {topPlayers.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">
                Top {TOP_PLAYERS_SHOWN} receivers by season PPR points
              </h2>
              <TopPlayersTable
                players={topPlayers}
                selectedPlayerId={selectedPlayer?.player_id ?? null}
                onSelect={setSelectedPlayer}
              />
            </section>
          )}

          {/* Accuracy is secondary, so if it fails to load the projections still show. */}
          {accuracyQuery.data && <AccuracyPanel accuracy={accuracyQuery.data} />}

          <ProjectLog />
        </div>
      </main>
    </div>
  );
}
