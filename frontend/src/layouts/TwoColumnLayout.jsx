/**
 * Asymmetric two-column canvas used by the role dashboards: a wide main
 * workspace (operational content) and a 340px right panel (contextual
 * utilities). Below the `lg` breakpoint the panel stacks under the main
 * column.
 */
export default function TwoColumnLayout({ main, aside }) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-6">{main}</div>
      <aside className="min-w-0 space-y-6">{aside}</aside>
    </div>
  );
}
