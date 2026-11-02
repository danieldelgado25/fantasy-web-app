/** One player's projection for their next game, as written by backend/train.py. */
export interface PlayerProjection {
  player_id: string;
  player_name: string;
  team: string;
  opponent_team: string;
  season: number;
  week: number;
  /** Position by official season-to-date PPR points. 1 is best. */
  rank: number;
  pred_targets: number;
  pred_rec: number;
  pred_rec_yds: number;
  pred_rec_td: number;
  pred_carries: number;
  pred_rushing_yards: number;
  pred_ppr_points: number;
}

/** The static file the daily job publishes. */
export interface ProjectionsFile {
  generated_at: string;
  players: PlayerProjection[];
}

/** The fields needed to list and select a player. */
export type Player = Pick<PlayerProjection, "player_id" | "player_name" | "team">;

/** One finished week of top-player points accuracy. Null means undefined that week. */
export interface AccuracyWeek {
  week: number;
  predicted: number;
  played: number;
  mae: number | null;
  baseline_mae: number | null;
  rank_correlation: number | null;
  baseline_rank_correlation: number | null;
}

/** A set of scored weeks and whether they meet the passing bar. */
export interface AccuracyResults {
  weeks: AccuracyWeek[];
  passed: boolean;
  /** Why the bar couldn't be checked yet, when that applies. */
  reason: string | null;
}

/** The accuracy file the daily job publishes. */
export interface AccuracyFile {
  generated_at: string;
  season: number;
  top_n: number;
  /** Predictions saved before kickoff. These are the ones that count. */
  live: AccuracyResults;
  /** Past weeks regenerated using only earlier games. Absent if never run. */
  replay?: AccuracyResults;
}

/** Location of the published projections, served from frontend/public. */
const PROJECTIONS_URL = "/data/projections.json";

/** Location of the published accuracy results, served from frontend/public. */
const ACCURACY_URL = "/data/accuracy.json";

/** Loads every player's projection. Throws so the page can show the failure. */
export async function fetchProjections(): Promise<ProjectionsFile> {
  const response = await fetch(PROJECTIONS_URL);
  if (!response.ok) {
    throw new Error(`Failed to load projections: ${response.status}`);
  }
  return response.json();
}

/** Loads the accuracy results. Throws so the page can show the failure. */
export async function fetchAccuracy(): Promise<AccuracyFile> {
  const response = await fetch(ACCURACY_URL);
  if (!response.ok) {
    throw new Error(`Failed to load accuracy results: ${response.status}`);
  }
  return response.json();
}
