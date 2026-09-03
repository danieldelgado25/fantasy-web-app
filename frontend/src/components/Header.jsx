/**
 * Header.jsx
 * ==========
 * Static page header. Split into its own component (rather than inlined in
 * App.jsx) purely for readability — App.jsx stays focused on data-fetching
 * and state, this stays focused on markup.
 */
export default function Header() {
  return (
    <header className="header">
      <div className="header__title-row">
        <h1 className="header__title">WR Projections</h1>
        <span className="header__subtitle">Next-week PPR fantasy points, Ridge regression</span>
      </div>
    </header>
  );
}
