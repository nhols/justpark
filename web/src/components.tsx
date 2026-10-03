import { memo, useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronRight, Search, X } from "lucide-react";

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
  const scrim = useRef<HTMLDivElement>(null);
  const swipe = useRef<{ x: number; y: number; time: number; horizontal?: boolean; dx: number }>(undefined);
  const setDrag = (dx: number, settle: boolean) => {
    scrim.current?.classList.toggle("settling", settle);
    scrim.current?.style.setProperty("--drawer-drag", `${dx}px`);
  };

  // Drag the panel right with a finger; release far enough, or flick, to dismiss it.
  return (
    <div
      className="scrim"
      ref={scrim}
      onMouseDown={close}
      onTouchStart={(event) => {
        const touch = event.touches[0];
        swipe.current = event.touches.length === 1 ? { x: touch.clientX, y: touch.clientY, time: performance.now(), dx: 0 } : undefined;
      }}
      onTouchMove={(event) => {
        const state = swipe.current;
        if (!state) return;
        const touch = event.touches[0];
        const dx = touch.clientX - state.x;
        const dy = touch.clientY - state.y;
        if (state.horizontal === undefined) {
          if (Math.hypot(dx, dy) < 10) return;
          state.horizontal = dx > 0 && Math.abs(dx) > Math.abs(dy);
        }
        if (!state.horizontal) return;
        state.dx = Math.max(0, dx);
        setDrag(state.dx, false);
      }}
      onTouchEnd={() => {
        const state = swipe.current;
        swipe.current = undefined;
        if (!state?.horizontal) return;
        const width = scrim.current?.querySelector(".drawer")?.getBoundingClientRect().width ?? 400;
        const flick = state.dx / (performance.now() - state.time) > .5 && state.dx > 30;
        if (flick || state.dx > width / 3) {
          setDrag(width + 40, true);
          setTimeout(close, 180);
        } else setDrag(0, true);
      }}
      onTouchCancel={() => {
        swipe.current = undefined;
        setDrag(0, true);
      }}
    >
      <button className="drawer-collapse" onMouseDown={(event) => event.stopPropagation()} onClick={close} aria-label="Collapse panel"><ChevronRight size={16} /></button>
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

// Steps through render stages one painted frame at a time, so heavy content can follow a light first paint.
export function useRenderStages(last: number) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (stage >= last) return;
    let timeout: number | undefined;
    const frame = requestAnimationFrame(() => { timeout = window.setTimeout(() => setStage(stage + 1), 0); });
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timeout);
    };
  }, [stage, last]);
  return stage;
}

function DataTableRows<T extends object>({ rows, columns, onSelect }: {
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

// Memoised so the long bookings table isn't re-rendered when only the calendar changes.
export const DataTable = memo(DataTableRows) as typeof DataTableRows;

export function SearchBox({ value, onChange, placeholder = "Search" }: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search"><Search size={16} /><input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></label>
  );
}
