import EmptyState from "./EmptyState";
import LoadingState from "./LoadingState";

/**
 * Generic table.
 * columns: [{ key, header, render?(row) }]
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
    <div className="overflow-x-auto rounded-card border border-border bg-card shadow-soft">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface text-xs uppercase tracking-wide text-muted">
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-4 py-3 font-medium">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-border last:border-0 ${
                onRowClick ? "cursor-pointer hover:bg-surface" : ""
              }`}
            >
              {columns.map((column) => (
                <td key={column.key} className="px-4 py-3 text-ink">
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
