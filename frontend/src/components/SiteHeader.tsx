import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { StadiumHeader } from "@/components/StadiumHeader";
import { fetchProjections } from "@/lib/api";

/** One tab: its page address and the label shown for it. */
interface Tab {
  /** Route path the tab opens. Add a route here when it gets a tab. */
  to: "/" | "/start-sit" | "/injuries" | "/accuracy" | "/log";
  /** Text on the tab. */
  label: string;
}

/** Every tab, in display order. Each is its own page so it can be linked to directly. */
const TABS: Tab[] = [
  { to: "/", label: "Projections" },
  { to: "/start-sit", label: "Start/Sit" },
  { to: "/injuries", label: "Injuries" },
  { to: "/accuracy", label: "Accuracy" },
  { to: "/log", label: "Log" },
];

/** Shared look for every tab; the active one is highlighted by Link's activeProps. */
const TAB_CLASS =
  "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground";

/** Header shown on every page: title, disclaimer, last update time and the tab bar. */
export function SiteHeader() {
  // Same query key as the pages, so the header doesn't download the file a second time.
  const projectionsQuery = useQuery({ queryKey: ["projections"], queryFn: fetchProjections });
  const generatedAt = projectionsQuery.data?.generated_at;

  return (
    <StadiumHeader>
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-bold">WR Projection Tool</h1>
        <p className="text-muted-foreground text-sm">
          Fantasy football projections for NFL wide receivers
        </p>
        <p className="text-muted-foreground mt-2 text-xs">
          Estimates from a statistical model trained on past NFL games, not guarantees. Injuries and
          late news may not be reflected.
          {generatedAt && ` Updated ${new Date(generatedAt).toLocaleString()}.`}
        </p>
        {/* Wraps onto a second line on narrow phones instead of scrolling sideways. */}
        <nav aria-label="Sections" className="mt-4 flex flex-wrap gap-1">
          {TABS.map((tab) => (
            <Link
              key={tab.to}
              to={tab.to}
              // Without exact, "/" would count as active on every page.
              activeOptions={{ exact: true }}
              // Link also sets aria-current="page" on the active tab for screen readers.
              activeProps={{ className: "bg-secondary text-foreground" }}
              className={TAB_CLASS}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </div>
    </StadiumHeader>
  );
}
