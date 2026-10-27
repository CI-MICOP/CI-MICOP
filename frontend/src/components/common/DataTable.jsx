import EmptyState from "./EmptyState";
import LoadingState from "./LoadingState";

/**
 * Generic table.
 * columns: [{ key, header, render?(row), align? }] - align "center" centres the
 *   header and its values (from sm up); left-aligned otherwise
 * rows: array of plain objects
 * rowKey: field name (or function) used as the React key per row
 */
export default function DataTable({
  columns,
  rows,
  rowKey = "id",
  isLoading = false,
  emptyMessage = "No records found.",
  onRowClick,
}) {
  if (isLoading) return <LoadingState label="Loading records..." />;
  if (!rows || rows.length === 0) return <EmptyState title={emptyMessage} />;

  const getKey = typeof rowKey === "function" ? rowKey : (row) => row[rowKey];

  return (
    // No fixed minimum width: columns fit their panel and cell text wraps
    // between words. Below the `sm` breakpoint each row is stacked as a
    // card of "header: value" lines (headers come from data-label, CSS only,
    // so the markup is the same at every width). overflow-x-auto stays only
    // as a last resort for a single word too long for its column.
    <div className="overflow-x-auto rounded-card border border-border bg-card shadow-soft">
      <table className="w-full table-auto text-left text-sm [overflow-wrap:break-word] max-sm:block">
        <thead className="max-sm:hidden">
          <tr className="border-b border-border bg-surface text-xs uppercase tracking-wide text-muted">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-4 py-3 align-middle font-medium ${column.align === "center" ? "text-center" : ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="max-sm:block">
          {rows.map((row) => (
            <tr
              key={getKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-border last:border-0 max-sm:block max-sm:py-2 ${
                onRowClick ? "cursor-pointer hover:bg-surface" : ""
              }`}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  data-label={typeof column.header === "string" ? column.header : undefined}
                  className={`px-4 py-3 align-middle text-ink ${column.align === "center" ? "sm:text-center" : ""} max-sm:flex max-sm:items-center max-sm:justify-between
                    max-sm:gap-4 max-sm:py-1.5 max-sm:text-right max-sm:before:shrink-0 max-sm:before:text-left
                    max-sm:before:text-xs max-sm:before:font-medium max-sm:before:uppercase
                    max-sm:before:tracking-wide max-sm:before:text-muted max-sm:before:content-[attr(data-label)]`}
                >
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
