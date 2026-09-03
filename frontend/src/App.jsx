/**
 * App.jsx
 * =======
 *
 * WHY STATE LIVES HERE
 * ----------------------
 * App.jsx is the only component that calls the API service layer
 * (src/api/projectionsApi.js) and the only component that holds the
 * season/week/team filter state. Everything below it (FilterBar,
 * ProjectionsTable, ModelInfoBanner) is a "presentational" component that
 * just renders whatever props it's given. This is the same shape as the
 * backend's routes -> services split: one layer owns "what are we doing and
 * why", the rest just renders/formats. It also means there's exactly one
 * `useEffect` that re-fetches projections, triggered by exactly one thing
 * (the filters changing) — easy to reason about, easy to add a loading
 * spinner or error banner to in one place.
 */
import { useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import FilterBar from "./components/FilterBar.jsx";
import ProjectionsTable from "./components/ProjectionsTable.jsx";
import ModelInfoBanner from "./components/ModelInfoBanner.jsx";
import { getProjections, getTeams, getModelInfo } from "./api/projectionsApi.js";

const DEFAULT_SEASON = 2024;
const DEFAULT_WEEK = 6; // matches the week the backend was live-tested against

export default function App() {
  const [season, setSeason] = useState(DEFAULT_SEASON);
  const [week, setWeek] = useState(DEFAULT_WEEK);
  const [team, setTeam] = useState(null);

  const [teams, setTeams] = useState([]);
  const [projections, setProjections] = useState([]);
  const [modelInfo, setModelInfo] = useState(null);

  const [status, setStatus] = useState("loading"); // "loading" | "ready" | "error"
  const [errorMessage, setErrorMessage] = useState(null);

  // Model metadata doesn't depend on filters — fetch it once on mount.
  useEffect(() => {
    getModelInfo()
      .then(setModelInfo)
      .catch(() => {
        // Non-critical: the projections table still works without this
        // banner, so a failure here shouldn't block the rest of the page.
      });
  }, []);

  // Team options depend only on the selected season, not the week — refetch
  // when season changes so the dropdown reflects teams that actually have
  // data for that year (handles relocations/rebrands automatically).
  useEffect(() => {
    getTeams(season)
      .then(setTeams)
      .catch(() => setTeams([]));
  }, [season]);

  // The core data fetch: re-run whenever season, week, or team changes.
  useEffect(() => {
    let cancelled = false; // guards against a stale response overwriting a newer one
    setStatus("loading");

    getProjections({ season, week, team })
      .then((data) => {
        if (cancelled) return;
        setProjections(data.projections);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setErrorMessage(err.message);
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [season, week, team]);

  return (
    <div className="app">
      <Header />

      <main className="app__main">
        <FilterBar
          season={season}
          week={week}
          team={team}
          teams={teams}
          onSeasonChange={setSeason}
          onWeekChange={setWeek}
          onTeamChange={setTeam}
        />

        <ModelInfoBanner modelInfo={modelInfo} />

        {status === "loading" && <p className="status-line">Loading projections…</p>}

        {status === "error" && (
          <div className="error-state">
            <p>Couldn't load projections: {errorMessage}</p>
            <p className="error-state__hint">
              Is the backend running? Start it with <code>python run.py</code> from{" "}
              <code>backend/</code>.
            </p>
          </div>
        )}

        {status === "ready" && <ProjectionsTable projections={projections} />}
      </main>
    </div>
  );
}
