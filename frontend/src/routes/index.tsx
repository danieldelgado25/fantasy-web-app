import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Intro } from "@/components/Intro";
import { PlayerSearch } from "@/components/PlayerSearch";
import { PlayerTracker } from "@/components/PlayerTracker";
import { ProjectionPanel } from "@/components/ProjectionPanel";
import { TopPlayersTable } from "@/components/TopPlayersTable";
import { fetchAccuracy, fetchPlayerHistory, fetchProjections, type Player } from "@/lib/api";

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

  // Weekly projected vs actual points, shown under the selected player's projection.
  const historyQuery = useQuery({
    queryKey: ["player-history"],
    queryFn: fetchPlayerHistory,
  });

  const players = projectionsQuery.data?.players ?? [];
  const topPlayers = players.filter((p) => p.rank <= TOP_PLAYERS_SHOWN);
  const selectedProjection = players.find((p) => p.player_id === selectedPlayer?.player_id) ?? null;

  // The shared header, tab bar and page frame come from __root.tsx.
  return (
    <div className="space-y-6">
      <Intro accuracy={accuracyQuery.data} />

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

      {/* Hidden until a player is picked and the history file has loaded. */}
      {selectedProjection && historyQuery.data && (
        <PlayerTracker
          weeks={historyQuery.data.players[selectedProjection.player_id] ?? []}
          reliability={historyQuery.data.reliability[selectedProjection.player_id] ?? null}
        />
      )}

      {topPlayers.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">
            Top {TOP_PLAYERS_SHOWN} receivers by season PPR points
          </h2>
          <TopPlayersTable
            players={topPlayers}
            selectedPlayerId={selectedPlayer?.player_id ?? null}
            onSelect={setSelectedPlayer}
          />
        </section>
      )}
    </div>
  );
}
