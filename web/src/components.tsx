import type { ReactNode } from "react";
import { Search, X } from "lucide-react";

export function Metric({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </article>
  );
}

export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  format = String,
}: {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  format?: (value: T) => string;
}) {
  return (
    <div className="segmented">
      {options.map((option) => (
        <button className={option === value ? "active" : ""} onClick={() => onChange(option)} key={option}>
          {format(option)}
        </button>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Drawer({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  return (
    <div className="scrim" onMouseDown={close}>
      <aside className="drawer" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="icon-button" onClick={close} aria-label="Close"><X size={20} /></button>
        </header>
        {children}
      </aside>
    </div>
  );
}

export type Column<T> = { key: keyof T; label: string; render?: (row: T) => ReactNode };

export function DataTable<T extends object>({ rows, columns, onSelect }: {
  rows: T[];
  columns: Column<T>[];
  onSelect?: (row: T) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={String(column.key)}>{column.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} onClick={() => onSelect?.(row)} className={onSelect ? "selectable" : ""}>
              {columns.map((column) => <td key={String(column.key)}>{column.render?.(row) ?? String(row[column.key] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder = "Search" }: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search"><Search size={16} /><input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></label>
  );
}
