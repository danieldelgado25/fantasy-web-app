export interface Player {
  player_id: string;
  player_name: string;
  team: string;
}

export interface Projection {
  player_id: string;
  player_name: string;
  team: string;
  opponent_team: string;
  season: number;
  week: number;
  projected_ppr_points: number;
  model_version: string;
}

const MOCK_PLAYERS: Player[] = [
  { player_id: "00-0036963", player_name: "Jaxon Smith-Njigba", team: "SEA" },
  { player_id: "00-0034855", player_name: "Ja'Marr Chase", team: "CIN" },
  { player_id: "00-0036389", player_name: "Amon-Ra St. Brown", team: "DET" },
  { player_id: "00-0037234", player_name: "Puka Nacua", team: "LAR" },
  { player_id: "00-0036160", player_name: "CeeDee Lamb", team: "DAL" },
];

const MOCK_PROJECTIONS: Record<string, Projection> = {
  "00-0036963": {
    player_id: "00-0036963",
    player_name: "Jaxon Smith-Njigba",
    team: "SEA",
    opponent_team: "NE",
    season: 2026,
    week: 1,
    projected_ppr_points: 14.82,
    model_version: "ridge-v1",
  },
  "00-0034855": {
    player_id: "00-0034855",
    player_name: "Ja'Marr Chase",
    team: "CIN",
    opponent_team: "PIT",
    season: 2026,
    week: 1,
    projected_ppr_points: 18.45,
    model_version: "ridge-v1",
  },
};

function getBaseUrl(): string | undefined {
  return import.meta.env.VITE_API_BASE_URL;
}

export async function fetchPlayers(): Promise<Player[]> {
  const baseUrl = getBaseUrl();
  if (!baseUrl) {
    return Promise.resolve(MOCK_PLAYERS);
  }

  const response = await fetch(`${baseUrl}/api/players`);
  if (!response.ok) {
    throw new Error(`Failed to fetch players: ${response.status}`);
  }
  return response.json();
}

export async function fetchProjection(playerId: string): Promise<Projection | null> {
  const baseUrl = getBaseUrl();
  if (!baseUrl) {
    const mock = MOCK_PROJECTIONS[playerId];
    if (!mock) {
      return null;
    }
    return Promise.resolve(mock);
  }

  const response = await fetch(`${baseUrl}/api/projections?player_id=${encodeURIComponent(playerId)}`);
  if (response.status === 501) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch projection: ${response.status}`);
  }
  return response.json();
}
