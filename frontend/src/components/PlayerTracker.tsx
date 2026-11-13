import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PlayerHistoryWeek } from "@/lib/api";

interface PlayerTrackerProps {
  /** The selected player's finished weeks, oldest first. Empty before any finished game. */
  weeks: PlayerHistoryWeek[];
}

/** Hover text for the Replay tag, explaining why those weeks count less. */
const REPLAY_NOTE =
  "Re-run after the fact using only games before that week. Only live predictions were saved before kickoff.";

/** Formats points to one decimal, or a dash when there's no value. */
function points(value: number | null): string {
  return value === null ? "–" : value.toFixed(1);
}

/** Formats a difference with an explicit sign, so beats and misses read at a glance. */
function signed(value: number | null): string {
  if (value === null) return "–";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

/**
 * The selected player's weekly projected vs actual PPR points. Collapsed by default
 * using a native <details>, so it needs no state or extra component.
 */
export function PlayerTracker({ weeks }: PlayerTrackerProps) {
  return (
    <details className="rounded-lg border bg-card p-4">
      <summary className="cursor-pointer text-sm font-medium">
        Prediction history ({weeks.length} {weeks.length === 1 ? "week" : "weeks"})
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
            </TableRow>
          </TableHeader>
          <TableBody>
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
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </details>
  );
}
