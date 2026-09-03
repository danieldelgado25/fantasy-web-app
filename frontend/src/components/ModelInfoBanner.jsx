/**
 * ModelInfoBanner.jsx
 * ===================
 * Surfaces the honesty check from training: does the model actually beat a
 * naive "predict their recent average" baseline? Showing this in the UI
 * (rather than burying it in a metrics.json only Daniel ever opens) is a
 * deliberate choice — a fantasy projection tool that can't show its own
 * model beats a dumb heuristic shouldn't be presenting itself as authoritative.
 */
export default function ModelInfoBanner({ modelInfo }) {
  if (!modelInfo) return null;

  const ridgeTest = modelInfo.metrics?.ridge?.test;
  const baselineTest = modelInfo.metrics?.baseline_rolling_avg?.test;
  const beats = modelInfo.metrics?.beats_baseline_on_test_rmse;

  if (!ridgeTest || !baselineTest) return null;

  return (
    <div className="model-banner">
      <span className="model-banner__stat">
        Model RMSE <strong>{ridgeTest.rmse}</strong>
      </span>
      <span className="model-banner__divider">vs</span>
      <span className="model-banner__stat model-banner__stat--muted">
        rolling-avg baseline <strong>{baselineTest.rmse}</strong>
      </span>
      <span className={`model-banner__verdict ${beats ? "model-banner__verdict--good" : "model-banner__verdict--bad"}`}>
        {beats ? "beats baseline" : "does not beat baseline"}
      </span>
    </div>
  );
}
