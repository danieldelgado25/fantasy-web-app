import type { AccuracyFile, AccuracyResults } from "@/lib/api";

interface IntroProps {
  /** Accuracy results, or undefined while loading or if they failed to load. */
  accuracy: AccuracyFile | undefined;
}

/** Average model and baseline misses across weeks where both were defined. */
interface Headline {
  modelMiss: number;
  baselineMiss: number;
  weeks: number;
}

/** Averages the weekly misses, skipping weeks where either value is undefined. */
function summarize(results: AccuracyResults): Headline | null {
  const scored = results.weeks.filter((w) => w.mae !== null && w.baseline_mae !== null);
  if (scored.length === 0) return null;
  const mean = (values: number[]) => values.reduce((sum, v) => sum + v, 0) / values.length;
  return {
    modelMiss: mean(scored.map((w) => w.mae!)),
    baselineMiss: mean(scored.map((w) => w.baseline_mae!)),
    weeks: scored.length,
  };
}

/**
 * What the project is and its headline result. Live results are preferred; until any
 * exist, the replay result is shown and labeled as a test so the two are never confused.
 */
export function Intro({ accuracy }: IntroProps) {
  const live = accuracy && summarize(accuracy.live);
  const replay = accuracy?.replay && summarize(accuracy.replay);
  const headline = live ?? replay;

  return (
    <section className="space-y-3">
      <p className="text-sm leading-relaxed">
        A model that predicts each NFL wide receiver&apos;s PPR fantasy points for their next game,
        using only information available before kickoff. It fits one Ridge regression per stat
        on nflreadpy data, refreshes daily, and is scored in public against a simple baseline:
        each player&apos;s average over their last 3 games.
      </p>
      {headline && (
        <div className="rounded-lg border bg-card p-4">
          <p className="text-muted-foreground text-xs uppercase tracking-wide">
            {live ? "Live predictions" : "Test run on past weeks, not live predictions"}
          </p>
          <p className="mt-1 text-sm">
            Missed by{" "}
            <span className="text-primary text-2xl font-bold">
              {headline.modelMiss.toFixed(2)}
            </span>{" "}
            points per player on average, vs {headline.baselineMiss.toFixed(2)} for the last-3
            average, over {headline.weeks} weeks.
          </p>
        </div>
      )}
    </section>
  );
}
