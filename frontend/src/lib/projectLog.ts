/** One entry in the public record of how the project has changed and why. */
export interface ProjectLogEntry {
  /** When the change was made, as YYYY-MM-DD. */
  date: string;
  /** What changed or was tested. */
  title: string;
  /** The reason for doing it. */
  why: string;
  /** What was measured or decided as a result. */
  result: string;
}

/** Public source code, so visitors can check the work behind each entry. */
export const REPOSITORY_URL = "https://github.com/danieldelgado25/fantasy-web-app";

/**
 * Newest first. Add an entry whenever the model, its evaluation or the site changes in a
 * way worth explaining, including tests that didn't work out. State which players and
 * seasons each MAE covers, because top-20 and all-WR figures differ a lot.
 */
export const PROJECT_LOG: ProjectLogEntry[] = [
  {
    date: "2026-11-03",
    title: "Made the prediction freeze an enforced rule",
    why: "That predictions are saved before kickoff was only checkable by reading git history.",
    result:
      "A check now runs in CI and in the daily job before it pushes. It fails if any commit added, edited or removed a prediction for a game that had already started.",
  },
  {
    date: "2026-11-03",
    title: "Tested scaling the inputs and tuning the penalty",
    why: "Ridge penalizes each input by its scale, so unscaled yards (0-200) and target share (0-1) were treated very differently, and the penalty was fixed at 1.0.",
    result:
      "Scaling with a penalty tuned by season or each week stayed within noise for each week's top 20: ranking +0.005 and MAE -0.010 over 2023-2025, then -0.004 and +0.010 on 2026. The model is unchanged.",
  },
  {
    date: "2026-11-03",
    title: "Made the results easier to read",
    why: "A review pointed out that MAE figures for different player sets looked contradictory, and that the ranking metric was never named.",
    result:
      "Each MAE now says which players and seasons it covers, ranking is named as Spearman rank correlation, and a How it works section lists the seven models. The test run leads the page until four live weeks are scored.",
  },
  {
    date: "2026-11-02",
    title: "First production deployment",
    why: "The site is meant to show how the model is built and re-evaluated, so publishing it doesn't need to wait for a perfect model.",
    result:
      "The site is deployed on Vercel, and live prediction tracking keeps running in public. Scoring against the passing bar continues as weeks finish.",
  },
  {
    date: "2026-11-02",
    title: "Tested better ways to project touchdowns",
    why: "Touchdowns cause many of the biggest points misses, so I tried count models, longer player history, expected touchdowns and red-zone targets.",
    result:
      "The best combination looked better on 2023-2025 but worse on 2026, so none were added. With so few touchdowns per game, they remain hard to predict.",
  },
  {
    date: "2026-11-02",
    title: "Security review before going public",
    why: "The deployment platform blocked the build over a critical cross-site scripting flaw in the web framework.",
    result:
      "Upgraded the framework rather than using the override to deploy anyway. Scanned the full git history for secrets, found none, and updated the build tools with known issues.",
  },
  {
    date: "2026-11-02",
    title: "Tested 10 groups of player-opportunity data",
    why: "The model ranks volume (catches 0.38) better than touchdowns (0.18), so better opportunity data looked like the next thing to try.",
    result:
      "None beat the normal week-to-week noise, so none were added. Expected production and teammates ruled out stay under consideration.",
  },
  {
    date: "2026-11-02",
    title: "Tested past prediction errors and other algorithms",
    why: "To find out whether the model could learn from how far off it had been, or whether a more complex algorithm would do better.",
    result:
      "Neither clearly improved on Ridge regression across 2023-2025 and 2026, so the simpler model stayed. Touchdowns account for many of the biggest misses.",
  },
  {
    date: "2026-11-02",
    title: "Replaced a ranking target that was wrong",
    why: "I had set a fixed ranking score of 0.30. Over 2023-2025, a 4-week average swung from 0.05 to 0.37, so passing would have been largely luck.",
    result:
      "The model must now beat a simple last-3-games average, which it did in 80% of past 4-week windows. Prediction tracking now scores against this bar.",
  },
  {
    date: "2026-11-02",
    title: "Added next-game context the correct way",
    why: "Home or away, dome and betting lines had been removed because training used the game just played, while predictions used the next game.",
    result:
      "Training now uses the game being predicted. Replaying 2023-2025 week by week for each week's top 20 receivers, ranking rose from 0.241 to 0.258 and MAE fell from 6.712 to 6.673: a small gain, but the only input that helped in both periods tested.",
  },
  {
    date: "2026-11-02",
    title: "Started saving predictions before kickoff",
    why: "Scoring a model on past games is useful, but only predictions saved in advance prove what it could really do.",
    result:
      "Each prediction is committed to the public repository and freezes at kickoff, so the history shows it wasn't edited afterwards. Scoring begins with week 9 of 2026.",
  },
  {
    date: "2026-11-01",
    title: "Corrected the baseline and switched to official scoring",
    why: "Averages were skipping each player's latest game, and the points formula left out rushing, fumbles and 2-point conversions.",
    result:
      "Across every WR game of the 2025 season, baseline MAE improved from 4.97 to 4.94 and the model's from 4.68 to 4.67. This includes low-usage receivers, so it runs lower than top-20 figures. Points now match official PPR totals.",
  },
  {
    date: "2026-11-01",
    title: "Removed weather from the model",
    why: "Game-time weather isn't known before kickoff, which conflicts with the project's rule against using future information.",
    result:
      "Accuracy was unchanged across every WR game of 2025 (MAE 4.676 vs 4.675), and usable training rows rose from 6,117 to 10,640.",
  },
];
