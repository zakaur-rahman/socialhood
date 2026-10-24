import type { ReactNode } from "react";

/**
 * The chart's numbers as a table for screen readers: the same values the picture draws, every
 * one reachable without hovering. Cells are text (`textContent`), never markup.
 */
export function ChartTable({ caption, columns, rows }: { caption: string; columns: string[]; rows: { key: string; cells: ReactNode[] }[] }) {
  return (
    <table className="sr-only" data-testid="chart-table">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {columns.map((column, index) => (
            <th key={`${index}-${column}`} scope="col">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            {row.cells.map((cell, index) => (index === 0 ? <th key={index} scope="row">{cell}</th> : <td key={index}>{cell}</td>))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
