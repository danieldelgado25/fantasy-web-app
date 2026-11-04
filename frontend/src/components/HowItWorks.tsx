/** One projected stat and the plain-language name shown for it. */
interface ModelStat {
  /** Column name in the pipeline, shown so reviewers can find it in the code. */
  column: string;
  /** What the stat means. */
  label: string;
}

/**
 * The stats that each get their own Ridge model. Mirrors PREDICTED_STATS in
 * backend/wr_predictor/stats.py, so update both together.
 */
const MODEL_STATS: ModelStat[] = [
  { column: "targets", label: "Targets" },
  { column: "rec", label: "Catches" },
  { column: "rec_yds", label: "Receiving yards" },
  { column: "rec_td", label: "Receiving touchdowns" },
  { column: "carries", label: "Carries" },
  { column: "rushing_yards", label: "Rushing yards" },
  { column: "ppr_points", label: "PPR points" },
];

/** What a technical reviewer asks first: the inputs, the models and where the points come from. */
export function HowItWorks() {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">How it works</h2>
      <ol className="list-decimal space-y-2 pl-5 text-sm">
        <li>
          <span className="font-medium">Inputs.</span> For each receiver, their last two games and
          3- and 5-game averages of points, catches, targets, yards, touchdowns, target share and
          air-yards share, plus the next game&apos;s home or away, dome, betting total and implied
          team total. Carries and rushing yards feed only the two rushing models. Nothing from the
          game being predicted is used.
        </li>
        <li>
          <span className="font-medium">Models.</span> One Ridge regression per stat below, each
          trained on every regular-season WR game since 2021 and retrained daily.
        </li>
        <li>
          <span className="font-medium">Points.</span> The PPR projection comes from its own model,
          trained directly on official PPR totals. It is not added up from the other six, which are
          shown to explain it.
        </li>
        {/* Says what the Start/Sit tab shows that the model doesn't use, so the two aren't confused. */}
        <li>
          <span className="font-medium">Not an input.</span> The Start/Sit tab also shows how many
          WR points each opponent allows per game. The model doesn&apos;t use it: a few games against
          uneven receiver groups make it too inconsistent to rely on.
        </li>
      </ol>
      <ul className="flex flex-wrap gap-2">
        {MODEL_STATS.map((stat) => (
          <li key={stat.column} className="rounded-md border bg-card px-2 py-1 text-xs">
            {stat.label} <code className="text-muted-foreground">{stat.column}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
