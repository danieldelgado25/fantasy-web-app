import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PlayerHistoryWeek, PlayerReliability } from "@/lib/api";

interface PlayerTrackerProps {
  /** The selected player's finished weeks, oldest first. Empty before any finished game. */
  weeks: PlayerHistoryWeek[];
  /** This season's grade and game counts. Null when the player has no games this season. */
  reliability: PlayerReliability | null;
}

/** Hover text for the Replay tag, explaining why those weeks count less. */
const REPLAY_NOTE =
  "Re-run after the fact using only games before that week. Only live predictions were saved before kickoff.";

/** Why week 1 has no projection, shown under the table and on the placeholder row. */
const WEEK_ONE_NOTE =
  "Week 1 isn't projected: no games had been played this season, so every input would come from last season. Rookies have no history, and players who changed teams would be judged on their old role.";

/** Formats points to one decimal, or a dash when there's no value. */
function points(value: number | null): string {
  return value === null ? "–" : value.toFixed(1);
}

/** Formats a difference with an explicit sign, so beats and misses read at a glance. */
function signed(value: number | null): string {
  if (value === null) return "–";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

/** The grade line, e.g. "B (7 of 9 games at 10+)". */
function gradeLabel(r: PlayerReliability): string {
  const count = `${r.games_10_plus} of ${r.games} games at 10+`;
  return r.grade === null ? `Not graded (${r.games} of 4 games needed)` : `${r.grade} (${count})`;
}

/** Hover text with the rates behind the grade. */
function gradeNote(r: PlayerReliability): string {
  const pct = (rate: number) => `${Math.round(rate * 100)}%`;
  return `Duds (under 5): ${pct(r.dud_rate)}. Booms (20+): ${pct(r.boom_rate)}. Duds with targets at or above average: ${r.volume_held_duds}.`;
}

/**
 * The selected player's weekly projected vs actual PPR points. Collapsed by default
 * using a native <details>, so it needs no state or extra component.
 */
export function PlayerTracker({ weeks, reliability }: PlayerTrackerProps) {
  return (
    <details className="rounded-lg border bg-card p-4">
      <summary className="cursor-pointer text-sm font-medium">
        Prediction history ({weeks.length} {weeks.length === 1 ? "week" : "weeks"})
        {/* Shown on the collapsed line too, so the grade is visible without opening it. */}
        {reliability && (
          <span className="ml-2 text-muted-foreground" title={gradeNote(reliability)}>
            · Reliability: {gradeLabel(reliability)}
          </span>
        )}
      </summary>

      {weeks.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No finished games yet.</p>
      ) : (
        <Table className="mt-3">
          <TableHeader>
            <TableRow>
              <TableHead>Week</TableHead>
              <TableHead className="text-right">Projected</TableHead>
              <TableHead className="text-right">Actual</TableHead>
              <TableHead className="text-right">Difference</TableHead>
              <TableHead>Tier</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Placeholder so the season visibly starts at week 1, with dashes instead of numbers. */}
            {!weeks.some((w) => w.week === 1) && (
              <TableRow title={WEEK_ONE_NOTE} className="text-muted-foreground">
                <TableCell>1</TableCell>
                <TableCell className="text-right">–</TableCell>
                <TableCell className="text-right">–</TableCell>
                <TableCell className="text-right">–</TableCell>
                <TableCell />
              </TableRow>
            )}
            {weeks.map((w) => (
              <TableRow key={w.week}>
                <TableCell className="space-x-2">
                  <span>{w.week}</span>
                  {/* Native title= gives a hover note without a tooltip library. */}
                  {w.replay && (
                    <Badge variant="outline" title={REPLAY_NOTE}>
                      Replay
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">{points(w.projected)}</TableCell>
                {/* A missing actual means the player didn't play that week. */}
                <TableCell
                  className="text-right"
                  title={w.actual === null ? "Did not play" : undefined}
                >
                  {points(w.actual)}
                </TableCell>
                <TableCell className="text-right">{signed(w.diff)}</TableCell>
                <TableCell>
                  {w.tier && (
                    <Badge variant={w.tier === "Dud" ? "outline" : "secondary"}>{w.tier}</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {weeks.length > 0 && !weeks.some((w) => w.week === 1) && (
        <p className="mt-3 text-xs text-muted-foreground">{WEEK_ONE_NOTE}</p>
      )}
    </details>
  );
}
