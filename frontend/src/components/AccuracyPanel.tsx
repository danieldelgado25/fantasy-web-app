import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AccuracyFile, AccuracyWeek } from "@/lib/api";

interface AccuracyPanelProps {
  accuracy: AccuracyFile;
}

/** Formats a value that can be undefined for a week, such as when every player tied. */
function formatValue(value: number | null): string {
  return value === null ? "n/a" : value.toFixed(2);
}

/** One row per finished week, comparing the model with the simple last-3-games average. */
function AccuracyTable({ weeks }: { weeks: AccuracyWeek[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Week</TableHead>
          <TableHead className="text-right">Players scored</TableHead>
          <TableHead className="text-right">Points off: model</TableHead>
          <TableHead className="text-right">Points off: last 3</TableHead>
          <TableHead className="text-right">Ranking: model</TableHead>
          <TableHead className="text-right">Ranking: last 3</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {weeks.map((week) => (
          <TableRow key={week.week}>
            <TableCell>{week.week}</TableCell>
            <TableCell className="text-right">{week.played}</TableCell>
            <TableCell className="text-right">{formatValue(week.mae)}</TableCell>
            <TableCell className="text-right">{formatValue(week.baseline_mae)}</TableCell>
            <TableCell className="text-right">{formatValue(week.rank_correlation)}</TableCell>
            <TableCell className="text-right">
              {formatValue(week.baseline_rank_correlation)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/**
 * How predictions compared with actual results. Live results and replays stay visibly
 * separate, because only live predictions were saved before the games were played.
 */
export function AccuracyPanel({ accuracy }: AccuracyPanelProps) {
  const { live, replay, top_n: topN } = accuracy;

  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-sm font-medium">How accurate is this?</h2>
        <p className="text-muted-foreground text-sm">
          Each week scores the top {topN} receivers. &quot;Points off&quot; is the average miss, so
          lower is better. &quot;Ranking&quot; is how well players were ordered, from -1 to 1, so
          higher is better. &quot;Last 3&quot; is simply each player&apos;s average over their last
          3 games.
        </p>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-medium">Live predictions</h3>
        <p className="text-muted-foreground text-sm">
          Saved before kickoff, then compared with what happened.
          {live.weeks.length === 0
            ? " No finished weeks yet."
            : live.passed
              ? " Currently beating the last-3 average over the latest 4 finished weeks."
              : " Not yet beating the last-3 average over 4 finished weeks."}
        </p>
        {live.weeks.length > 0 && <AccuracyTable weeks={live.weeks} />}
      </div>

      {replay && replay.weeks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Test run on past weeks</h3>
          <p className="text-muted-foreground text-sm">
            Regenerated later using only earlier games, so this is a test of the method rather than
            a record of predictions made in advance.
          </p>
          <AccuracyTable weeks={replay.weeks} />
        </div>
      )}
    </section>
  );
}
