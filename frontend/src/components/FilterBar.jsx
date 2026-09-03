/**
 * FilterBar.jsx
 * =============
 * Controlled inputs for season / week / team. This component holds no state
 * of its own and makes no API calls — it just renders the current filter
 * values and calls the `onChange` callbacks it's given. That keeps "what the
 * current filters are" living in exactly one place (App.jsx's state), which
 * is what actually drives the data fetch — a classic "lift state up" split
 * that avoids the filters and the fetched data ever disagreeing with each
 * other.
 */

// Training data covers 2016-2024 (see backend/training/train_model.py);
// projections can be requested for any of those seasons plus whatever the
// pipeline can build features for. Regular season is weeks 1-18 since 2021
// (17 games); using 18 as the upper bound covers both eras.
const SEASON_OPTIONS = Array.from({ length: 2024 - 2016 + 1 }, (_, i) => 2016 + i).reverse();
const WEEK_OPTIONS = Array.from({ length: 18 }, (_, i) => i + 1);

export default function FilterBar({ season, week, team, teams, onSeasonChange, onWeekChange, onTeamChange }) {
  return (
    <div className="filter-bar">
      <label className="filter-bar__field">
        <span className="filter-bar__label">Season</span>
        <select value={season} onChange={(e) => onSeasonChange(Number(e.target.value))}>
          {SEASON_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="filter-bar__field">
        <span className="filter-bar__label">Week</span>
        <select value={week} onChange={(e) => onWeekChange(Number(e.target.value))}>
          {WEEK_OPTIONS.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </label>

      <label className="filter-bar__field">
        <span className="filter-bar__label">Team</span>
        <select value={team ?? ""} onChange={(e) => onTeamChange(e.target.value || null)}>
          <option value="">All teams</option>
          {teams.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
