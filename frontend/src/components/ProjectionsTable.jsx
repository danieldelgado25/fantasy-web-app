/**
 * ProjectionsTable.jsx
 * ====================
 * Renders the ranked list of WR projections returned by the API. This
 * component is intentionally "dumb" — it takes a `projections` array as a
 * prop and renders it; it doesn't fetch data, doesn't know about filters,
 * and doesn't know the API exists. That makes it trivial to reuse (e.g. a
 * future "compare two weeks" view could render two of these side by side)
 * and trivial to test (pass in a fixed array, assert on the output).
 */
export default function ProjectionsTable({ projections }) {
  if (projections.length === 0) {
    return (
      <div className="empty-state">
        <p>No projections for this combination of season, week, and team.</p>
        <p className="empty-state__hint">
          Early-season weeks need prior games to compute rolling averages from — try a later week,
          or clear the team filter.
        </p>
      </div>
    );
  }

  return (
    <ol className="projections-list">
      {projections.map((row, index) => (
        <li key={row.player_id} className="projections-list__row">
          <span className="projections-list__rank">{index + 1}</span>

          <div className="projections-list__player">
            <span className="projections-list__name">{row.player_display_name ?? row.player_name}</span>
            <span className="projections-list__meta">
              <span className="team-badge">{row.team}</span>
              <span className="projections-list__vs">
                {" "}
                vs <span className="team-badge team-badge--muted">{row.opponent_team}</span>
              </span>
              <span className="projections-list__asof">
                {" "}
                &middot; as of Wk {row.week}
              </span>
            </span>
          </div>

          <span className="projections-list__points">{row.predicted_next_week_ppr.toFixed(1)}</span>
        </li>
      ))}
    </ol>
  );
}
