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

/** Location of the published projections, served from frontend/public. */
const PROJECTIONS_URL = "/data/projections.json";

/** Loads every player's projection. Throws so the page can show the failure. */
export async function fetchProjections(): Promise<ProjectionsFile> {
  const response = await fetch(PROJECTIONS_URL);
  if (!response.ok) {
    throw new Error(`Failed to load projections: ${response.status}`);
  }
  return response.json();
}
