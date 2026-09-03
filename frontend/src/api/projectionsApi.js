/**
 * projectionsApi.js
 * ==================
 *
 * WHY THIS FILE EXISTS
 * ---------------------
 * This is the frontend's equivalent of the backend's service layer: the ONLY
 * place in the React app that knows the API's base URL, its query-param
 * names, or how to turn a fetch() Response into usable data (or a thrown
 * error). Components never call `fetch()` directly — they call functions
 * exported from here. If the API's base URL changes (a different port in
 * production, a reverse-proxy path prefix, etc.) or an endpoint's shape
 * changes, this is the one file that needs to change; every component that
 * consumes projections keeps working unmodified.
 *
 * This mirrors the backend's own reasoning for `wr_pipeline_service.py` and
 * `model_service.py`: isolate the "how do we reach this dependency" logic
 * behind a small, stable function signature.
 */

// In dev, Vite serves the frontend on :5173 and Flask serves the API on
// :5000 (see backend/run.py). VITE_API_BASE_URL lets a production build
// point at wherever the API is actually deployed, without code changes.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

/**
 * Shared fetch wrapper: builds the URL, checks response.ok, and throws a
 * descriptive Error on failure so callers can just `await` and try/catch
 * once, instead of every call site re-checking `response.ok` by hand.
 */
async function apiGet(path, params = {}) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  const response = await fetch(url.toString());
  if (!response.ok) {
    // The backend returns {"error": "..."} on 4xx/5xx (see routes.py) —
    // surface that message when present, since it's usually more useful
    // than a bare HTTP status code ("season/week required", "model not
    // trained yet", etc.).
    let message = `Request to ${path} failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.error) message = body.error;
    } catch {
      // response body wasn't JSON — fall back to the generic message above
    }
    throw new Error(message);
  }
  return response.json();
}

/**
 * Fetch weekly WR projections.
 * @param {{season: number, week: number, team?: string, limit?: number}} params
 * @returns {Promise<{season: number, week: number, team: string|null, count: number, projections: object[]}>}
 */
export function getProjections({ season, week, team, limit }) {
  return apiGet("/api/projections", { season, week, team, limit });
}

/** Fetch the distinct team codes available for a season (for the filter dropdown). */
export function getTeams(season) {
  return apiGet("/api/teams", { season }).then((data) => data.teams);
}

/** Fetch training/eval metadata about the currently-loaded model. */
export function getModelInfo() {
  return apiGet("/api/model-info");
}
