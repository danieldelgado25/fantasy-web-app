import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AccuracyPanel } from "@/components/AccuracyPanel";
import { HowItWorks } from "@/components/HowItWorks";
import { Intro } from "@/components/Intro";
import { PlayerSearch } from "@/components/PlayerSearch";
import { ProjectionPanel } from "@/components/ProjectionPanel";
import { TopPlayersTable } from "@/components/TopPlayersTable";
import { Button } from "@/components/ui/button";
import { fetchAccuracy, fetchProjections, type Player } from "@/lib/api";
import { REPOSITORY_URL } from "@/lib/projectLog";

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

      {/* Accuracy is secondary, so if it fails to load the projections still show. */}
      {accuracyQuery.data && <AccuracyPanel accuracy={accuracyQuery.data} />}

      <HowItWorks />

      <Button asChild variant="outline" size="sm">
        <a href={REPOSITORY_URL}>Source code on GitHub</a>
      </Button>
    </div>
  );
}
