import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { InjuryIcon } from "@/components/InjuryIcon";
import { fetchInjuryNews } from "@/lib/api";

/** Past this age the feed is flagged as stale. Runs are normally at most ~18 hours apart. */
const STALE_HOURS = 24;

export const Route = createFileRoute("/injuries")({
  head: () => ({
    meta: [
      { title: "Injury News · WR Projection Tool" },
      {
        name: "description",
        content: "Every wide receiver on the injury report or a reserve list, newest first.",
      },
    ],
  }),
  component: InjuriesPage,
});

/** Whole hours between an ISO time and now. */
function hoursSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
}

/** "Nov 5, 3:20 AM" in the viewer's own time zone. */
function shortTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** The Injuries tab: every WR's current injury status, newest change first, with search. */
function InjuriesPage() {
  // What the viewer typed in the search box.
  const [search, setSearch] = useState("");
  const newsQuery = useQuery({ queryKey: ["injuries"], queryFn: fetchInjuryNews });

  const entries = newsQuery.data?.players ?? [];
  const query = search.trim().toLowerCase();
  const shown = query
    ? entries.filter(
        (e) => e.player_name.toLowerCase().includes(query) || e.team.toLowerCase().includes(query),
      )
    : entries;

  const generatedAt = newsQuery.data?.generated_at;
  const age = generatedAt ? hoursSince(generatedAt) : null;

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Every wide receiver on this week&apos;s official injury report or a reserve list, newest
        change first. Healthy players aren&apos;t listed.
      </p>

      {/* The feed only changes when the pipeline runs, so say how old it is. */}
      {generatedAt && age !== null && (
        <p className={`text-xs ${age >= STALE_HOURS ? "text-amber-500" : "text-muted-foreground"}`}>
          Updated {shortTime(generatedAt)} ({age < 1 ? "under an hour" : `${age} hours`} ago).
          {age >= STALE_HOURS &&
            " This is over a day old: check a live news source for the latest."}
        </p>
      )}

      <label className="block space-y-2 text-sm font-medium">
        <span>Search by player or team</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="e.g. Adams or LA"
          className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm font-normal"
        />
      </label>

      {newsQuery.isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {newsQuery.error && (
        <p className="text-destructive text-sm">Injury news couldn&apos;t be loaded.</p>
      )}

      {/* Empty states: a search with no match, or nobody on the report at all. */}
      {newsQuery.data && shown.length === 0 && (
        <p className="text-muted-foreground text-sm">
          {query
            ? `No recent injury news for "${search.trim()}". They aren't on this week's injury report or a reserve list.`
            : "No wide receivers are on the injury report or a reserve list right now."}
        </p>
      )}

      {shown.length > 0 && (
        <ul className="divide-y rounded-md border">
          {shown.map((entry) => (
            <li key={entry.player_id} className="space-y-1 px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">
                  {entry.player_name}{" "}
                  <span className="text-muted-foreground text-xs">{entry.team}</span>
                </span>
                <InjuryIcon status={entry.injury_status} note={entry.injury_note} />
              </div>
              <p className="text-muted-foreground text-xs">
                {entry.injury_note} · Week {entry.week} · First seen {shortTime(entry.first_seen)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
