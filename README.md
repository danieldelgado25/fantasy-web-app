# Fantasy Air

App description (paste as the initial prompt):

Build a fantasy football projection web app for NFL wide receivers. It's a single-page tool: the user searches/selects a WR from a dropdown, and the app shows that player's projected PPR fantasy points for their next game, along with basic context (team, opponent, week). This is an MVP for one demo use case — no accounts, no database, no multi-sport support yet. Use React + Tailwind CSS. All data comes from an external REST API (not Supabase) — use fetch against a base URL stored in an environment variable (VITE_API_BASE_URL), not a hardcoded localhost URL, so it can be pointed at a deployed backend later.

Pages/components needed (keep it to this — don't let Lovable add extra pages/features):

Single page, header with app name.

A searchable player dropdown/typeahead (calls GET /api/players, filters client-side or server-side, your call).

A result panel showing the selected player's projection (calls GET /api/projections?player_id=...).

Three states for the result panel: loading, error/"not available yet" (backend currently returns a 501 for this — handle it as "projection not available yet," not a crash), and success.

API contract to build against (mock this data in Lovable for now; I'll implement it server-side to match exactly):

GET /api/players →

[
  { "player_id": "00-0036963", "player_name": "Jaxon Smith-Njigba", "team": "SEA" },
  { "player_id": "00-0034855", "player_name": "Ja'Marr Chase", "team": "CIN" }
]


GET /api/projections?player_id=00-0036963 →

{
  "player_id": "00-0036963",
  "player_name": "Jaxon Smith-Njigba",
  "team": "SEA",
  "opponent_team": "NE",
  "season": 2026,
  "week": 1,
  "projected_ppr_points": 14.82,
  "model_version": "ridge-v1"
}



Explicitly don't build: authentication, a database, multi-sport support, historical charts, admin tooling. If Lovable suggests any of these, decline — MVP scope only.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/b32d8acf-ac1f-4ab2-a366-e10535f1a041).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
