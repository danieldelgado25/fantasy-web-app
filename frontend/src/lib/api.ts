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
  // Display-only details from nflreadpy. Optional: older files lack them, and any can be null.
  headshot_url?: string | null;
  team_logo_url?: string | null;
  jersey_number?: string | null;
  /** YYYY-MM-DD. */
  birth_date?: string | null;
  height_inches?: number | null;
  weight_lbs?: number | null;
  college?: string | null;
  years_exp?: number | null;
  /** Regular-season games and receiving totals for `season` so far. */
  season_games?: number | null;
  season_targets?: number | null;
  season_rec?: number | null;
  season_rec_yds?: number | null;
  season_rec_td?: number | null;
  // The upcoming game as the model saw it (backend player_info.game_context). Optional like above.
  /** 1 home, 0 away. */
  is_home?: number | null;
  /** 1 when played under a roof. */
  is_dome?: number | null;
  /** Betting total for the game. A neutral stand-in when line_posted is false. */
  game_total?: number | null;
  /** Points the betting line expects the player's team to score. */
  team_implied_total?: number | null;
  /** False until a real betting line exists for the game. */
  line_posted?: boolean | null;
  /** Kickoff date (YYYY-MM-DD) and time (HH:MM), US Eastern. */
  gameday?: string | null;
  gametime?: string | null;
  // Display only, not a model input (backend player_info.defense_vs_wr).
  /** WR PPR points the opponent allows per game this season. */
  opp_wr_points_allowed?: number | null;
  /** Opponent's rank by WR points allowed. 1 allows the most (easiest matchup). */
  opp_wr_allowed_rank?: number | null;
  // Display only, from the official injury report (backend player_info.add_injury_status).
  /** Worst status for the projected game. Null or absent means healthy. */
  injury_status?: InjuryStatus | null;
  /** Report details, e.g. "Questionable · Did not practice · Hamstring". */
  injury_note?: string | null;
}

/** Injury statuses, worst to best. IR is never sent today: IR players are left off the site. */
export type InjuryStatus = "IR" | "Out" | "Doubtful" | "DNP" | "Questionable";

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

/** One WR's current injury status in the news feed, as written by backend/write_injury_news.py. */
export interface InjuryNewsEntry {
  player_id: string;
  player_name: string;
  team: string;
  /** Week of the injury report or roster the status comes from. */
  week: number;
  injury_status: InjuryStatus;
  /** Report details, e.g. "Questionable · Did not practice · Hamstring". */
  injury_note: string;
  /** UTC ISO time the pipeline first saw this status. */
  first_seen: string;
}

/** The injury news file the daily job publishes. Entries are newest first. */
export interface InjuryNewsFile {
  generated_at: string;
  players: InjuryNewsEntry[];
}

/** Location of the published injury news feed, served from frontend/public. */
const INJURIES_URL = "/data/injuries.json";

/** Loads the injury news feed. Throws so the page can show the failure. */
export async function fetchInjuryNews(): Promise<InjuryNewsFile> {
  const response = await fetch(INJURIES_URL);
  if (!response.ok) {
    throw new Error(`Failed to load injury news: ${response.status}`);
  }
  return response.json();
}

/** One finished week of a player's projected vs actual PPR points, as written by backend/evaluate.py. */
export interface PlayerHistoryWeek {
  week: number;
  projected: number;
  /** Null when the player didn't play that week. */
  actual: number | null;
  /** Actual minus projected; positive means the player beat the projection. Null with no actual. */
  diff: number | null;
  /** PPR tier: Dud (<5), Low, Solid, Strong, Boom or NUCLEAR (30+). Null when the player didn't play. */
  tier: "Dud" | "Low" | "Solid" | "Strong" | "Boom" | "NUCLEAR" | null;
  /** True when the week was regenerated after the fact, not logged before kickoff. */
  replay: boolean;
}

/** A player's reliability this season, from every regular-season game they played. */
export interface PlayerReliability {
  /** A-F for this season's top 36 WRs, "Off the radar" for the rest, null under 4 games. */
  grade: string | null;
  games: number;
  games_10_plus: number;
  /** Share of games under 5 points. */
  dud_rate: number;
  /** Share of games at 20 points or more. */
  boom_rate: number;
  /** Duds where targets were at or above the player's season average. */
  volume_held_duds: number;
}

/** The player history file the daily job publishes, keyed by player_id. */
export interface PlayerHistoryFile {
  generated_at: string;
  season: number;
  players: Record<string, PlayerHistoryWeek[]>;
  reliability: Record<string, PlayerReliability>;
}

/** Location of the published player history, served from frontend/public. */
const PLAYER_HISTORY_URL = "/data/player_history.json";

/** Loads every player's weekly history. Throws so the page can show the failure. */
export async function fetchPlayerHistory(): Promise<PlayerHistoryFile> {
  const response = await fetch(PLAYER_HISTORY_URL);
  if (!response.ok) {
    throw new Error(`Failed to load player history: ${response.status}`);
  }
  return response.json();
}
