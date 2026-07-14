import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Drawer } from "./components";
import type { Booking, Dashboard, Observation, ObservationMonth } from "./types";

const LONDON = "Europe/London";
const LOAD_DAYS = 14;
const INITIAL_PAST_DAYS = 4;
const BIN_MINUTES = 15;
const londonFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: LONDON,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

type LondonParts = { key: string; minutes: number };
type Selection = { kind: "booking"; booking: Booking } | { kind: "observations"; observations: Observation[] };

function londonParts(value: string | Date): LondonParts {
  const parts = Object.fromEntries(londonFormatter.formatToParts(typeof value === "string" ? new Date(value) : value).map((part) => [part.type, part.value]));
  return { key: `${parts.year}-${parts.month}-${parts.day}`, minutes: Number(parts.hour) * 60 + Number(parts.minute) };
}

function addDays(key: string, amount: number) {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + amount));
  return date.toISOString().slice(0, 10);
}

function datesBetween(start: string, end: string) {
  const dates: string[] = [];
  for (let day = start; day <= end; day = addDays(day, 1)) dates.push(day);
  return dates;
}

function formatDay(key: string) {
  const [year, month, day] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, day)));
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON, weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(new Date(value));
}

function formatObservationTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function observationsEndpoint(month: string) {
  if (import.meta.env.DEV) return `${import.meta.env.BASE_URL}parking-observations/v1/${month}.json`;
  return `${import.meta.env.BASE_URL}api/observations?month=${encodeURIComponent(month)}`;
}

function inBooking(observation: Observation, booking: Booking) {
  const time = Date.parse(observation.observedAt);
  return Date.parse(booking.start) <= time && time < Date.parse(booking.end);
}

export function Observations({ data }: { data: Dashboard }) {
  const today = useMemo(() => londonParts(new Date()).key, []);
  const [days, setDays] = useState(() => datesBetween(addDays(today, -INITIAL_PAST_DAYS), addDays(today, 4)));
  const [months, setMonths] = useState<Map<string, ObservationMonth>>(() => new Map());
  const [selection, setSelection] = useState<Selection>();
  const [tableDay, setTableDay] = useState(today);
  const scroller = useRef<HTMLDivElement>(null);
  const olderSentinel = useRef<HTMLDivElement>(null);
  const newerSentinel = useRef<HTMLDivElement>(null);
  const fetching = useRef(new Set<string>());
  const prependHeight = useRef<number | undefined>(undefined);
  const positioned = useRef(false);
  const activeBookings = useMemo(() => data.bookings.filter((booking) => booking.status !== "cancelled"), [data.bookings]);

  useEffect(() => {
    const needed = [...new Set([...days, tableDay].map((day) => day.slice(0, 7)))];
    needed.forEach((month) => {
      if (months.has(month) || fetching.current.has(month)) return;
      fetching.current.add(month);
      fetch(observationsEndpoint(month), { cache: "no-store" })
        .then(async (response) => {
          if (response.status === 404 && import.meta.env.DEV) return { schemaVersion: 1, month, generatedAt: new Date().toISOString(), observations: [] } satisfies ObservationMonth;
          if (!response.ok) throw new Error(`Observation request failed (${response.status})`);
          return response.json() as Promise<ObservationMonth>;
        })
        .then((payload) => {
          if (payload.schemaVersion !== 1 || payload.month !== month || !Array.isArray(payload.observations)) throw new Error("Unsupported observation data");
          setMonths((current) => new Map(current).set(month, payload));
        })
        .catch(() => setMonths((current) => new Map(current).set(month, { schemaVersion: 1, month, generatedAt: new Date().toISOString(), observations: [] })))
        .finally(() => fetching.current.delete(month));
    });
  }, [days, months, tableDay]);

  useLayoutEffect(() => {
    if (!positioned.current && scroller.current) {
      scroller.current.scrollTop = scroller.current.scrollHeight * INITIAL_PAST_DAYS / days.length;
      positioned.current = true;
    }
    if (prependHeight.current === undefined || !scroller.current) return;
    scroller.current.scrollTop += scroller.current.scrollHeight - prependHeight.current;
    prependHeight.current = undefined;
  }, [days]);

  useEffect(() => {
    const root = scroller.current;
    const older = olderSentinel.current;
    const newer = newerSentinel.current;
    if (!root || !older || !newer) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        if (entry.target === older) {
          if (prependHeight.current !== undefined) return;
          prependHeight.current = root.scrollHeight;
          setDays((current) => [...datesBetween(addDays(current[0], -LOAD_DAYS), addDays(current[0], -1)), ...current]);
        } else {
          setDays((current) => [...current, ...datesBetween(addDays(current.at(-1)!, 1), addDays(current.at(-1)!, LOAD_DAYS))]);
        }
      });
    }, { root, rootMargin: "100px 0px", threshold: 0 });
    observer.observe(older);
    observer.observe(newer);
    return () => observer.disconnect();
  }, [days[0], days.at(-1)]);

  const allObservations = useMemo(() => [...months.values()].flatMap((month) => month.observations), [months]);
  const observationsByDay = useMemo(() => {
    const grouped = new Map<string, Observation[]>();
    allObservations.forEach((observation) => {
      const key = londonParts(observation.observedAt).key;
      grouped.set(key, [...(grouped.get(key) ?? []), observation]);
    });
    return grouped;
  }, [allObservations]);

  const selectedBooking = selection?.kind === "booking" ? selection.booking : selection?.observations.flatMap((observation) => activeBookings.filter((booking) => inBooking(observation, booking)))[0];
  const selectedObservations = selection?.kind === "observations"
    ? selection.observations
    : selection ? allObservations.filter((observation) => inBooking(observation, selection.booking)).sort((a, b) => a.observedAt.localeCompare(b.observedAt)) : [];
  const dayObservations = allObservations
    .filter((observation) => londonParts(observation.observedAt).key === tableDay)
    .sort((a, b) => a.observedAt.localeCompare(b.observedAt));

  return <>
    <section className="panel observations-panel">
      <div className="observations-title"><div><h2>Parking observations</h2><p>Parking spot status observations from video doorbell events, overlaid on JustPark bookings.</p></div><div className="observation-legend" aria-label="Timeline legend"><span className="legend-booking" /> booking <span className="legend-occupied" /> occupied <span className="legend-vacant" /> vacant <span className="legend-entering" /> entering <span className="legend-leaving" /> leaving</div></div>
      <div className="timeline-axis"><span /><div>{[0, 6, 12, 18, 24].map((hour) => <time key={hour} style={{ left: `${hour / 24 * 100}%` }}>{String(hour).padStart(2, "0")}:00</time>)}</div></div>
      <div className="observation-scroll" ref={scroller}>
        <div className="load-sentinel" ref={olderSentinel} />
        {days.map((day) => <TimelineDay
          key={day}
          day={day}
          bookings={activeBookings}
          observations={observationsByDay.get(day) ?? []}
          selected={day === tableDay}
          onDay={() => setTableDay(day)}
          onBooking={(booking) => setSelection({ kind: "booking", booking })}
          onObservations={(observations) => setSelection({ kind: "observations", observations })}
        />)}
        <div className="load-sentinel" ref={newerSentinel} />
      </div>
    </section>
    <section className="panel daily-observations">
      <div className="daily-observations-title">
        <div><h2>All observations</h2><p>{formatDay(tableDay)} · {dayObservations.length.toLocaleString()} observations</p></div>
        <div className="day-pagination" aria-label="Observation day">
          <button aria-label="Previous observation day" onClick={() => setTableDay((day) => addDays(day, -1))}>‹</button>
          <button onClick={() => setTableDay(today)}>Today</button>
          <button aria-label="Next observation day" onClick={() => setTableDay((day) => addDays(day, 1))}>›</button>
        </div>
      </div>
      {dayObservations.length ? <ObservationTable observations={dayObservations} onSelect={(observation) => setSelection({ kind: "observations", observations: [observation] })} /> : <p className="daily-observations-empty">No observations this day.</p>}
    </section>
    {selection && <ObservationInspector
      booking={selectedBooking}
      observations={selectedObservations}
      data={data}
      close={() => setSelection(undefined)}
    />}
  </>;
}

function TimelineDay({ day, bookings, observations, selected, onDay, onBooking, onObservations }: {
  day: string;
  bookings: Booking[];
  observations: Observation[];
  selected: boolean;
  onDay: () => void;
  onBooking: (booking: Booking) => void;
  onObservations: (observations: Observation[]) => void;
}) {
  const segments = bookings.flatMap((booking) => {
    const start = londonParts(booking.start);
    const end = londonParts(booking.end);
    if (start.key > day || end.key < day) return [];
    const startMinutes = start.key === day ? start.minutes : 0;
    const endMinutes = end.key === day ? end.minutes : 1440;
    return endMinutes > startMinutes ? [{ booking, startMinutes, endMinutes }] : [];
  });
  const bins = new Map<string, { bin: number; status: Observation["status"]; observations: Observation[] }>();
  observations.forEach((observation) => {
    const bin = Math.floor(londonParts(observation.observedAt).minutes / BIN_MINUTES);
    const key = `${bin}:${observation.status}`;
    const existing = bins.get(key);
    bins.set(key, { bin, status: observation.status, observations: [...(existing?.observations ?? []), observation] });
  });

  return <div className="timeline-row">
    <button className={`timeline-day ${selected ? "active" : ""}`} aria-pressed={selected} onClick={onDay}>{formatDay(day)}</button>
    <div className="timeline-track">
      {[0, 6, 12, 18, 24].map((hour) => <span className="timeline-gridline" key={hour} style={{ left: `${hour / 24 * 100}%` }} />)}
      {segments.map(({ booking, startMinutes, endMinutes }) => {
        const style = { "--start": `${startMinutes / 1440 * 100}%`, "--width": `${(endMinutes - startMinutes) / 1440 * 100}%` } as CSSProperties;
        return <Fragment key={booking.id}><button
          className="booking-band"
          style={style}
          aria-label={`Booking for ${booking.registration}`}
          onPointerUp={(event) => event.currentTarget.blur()}
          onClick={() => onBooking(booking)}
        /><span className="booking-band-label" style={style}>{booking.registration}</span></Fragment>;
      })}
      {[...bins].map(([key, { bin, status, observations: grouped }]) => {
        const kind = status === "car entering" ? "entering" : status === "car leaving" ? "leaving" : status;
        return <button
          key={key}
          className={`observation-marker ${kind}`}
          style={{ left: `${(bin * BIN_MINUTES + BIN_MINUTES / 2) / 1440 * 100}%`, "--marker-size": `${Math.min(16, 6 + Math.sqrt(grouped.length) * 2.5)}px` } as CSSProperties}
          aria-label={`${grouped.length} ${status} observation${grouped.length === 1 ? "" : "s"} around ${String(Math.floor(bin * BIN_MINUTES / 60)).padStart(2, "0")}:${String(bin * BIN_MINUTES % 60).padStart(2, "0")}`}
          onClick={() => onObservations(grouped)}
        />;
      })}
    </div>
  </div>;
}

function ObservationInspector({ booking, observations, data, close }: { booking?: Booking; observations: Observation[]; data: Dashboard; close: () => void }) {
  const vehicle = booking ? data.vehicles.find((item) => item.id === booking.vehicleId) : undefined;
  return <Drawer title={booking ? booking.registration : "Observations"} close={close}>
    {booking && <section className="inspector-section"><h3>Booking</h3><dl className="details booking-details">
      <div><dt>Start</dt><dd>{formatTimestamp(booking.start)}</dd></div>
      <div><dt>End</dt><dd>{formatTimestamp(booking.end)}</dd></div>
      <div><dt>Registration plate</dt><dd><span className="registration">{booking.registration}</span></dd></div>
      <div><dt>Vehicle colour</dt><dd>{vehicle?.colour ?? booking.vehicleColour ?? "—"}</dd></div>
      <div><dt>Vehicle make/model</dt><dd>{vehicle ? [vehicle.make, vehicle.model].filter(Boolean).join(" ") : booking.vehicle || "—"}</dd></div>
    </dl></section>}
    <section className="inspector-section"><h3>Observations</h3>
      {observations.length ? <ObservationTable observations={observations} className="inspector-table" /> : <p className="inspector-empty">No observations in this booking window.</p>}
    </section>
  </Drawer>;
}

function ObservationTable({ observations, className = "observations-table", onSelect }: { observations: Observation[]; className?: string; onSelect?: (observation: Observation) => void }) {
  return <div className={className}><table><thead><tr><th>Time</th><th>Status</th><th>Number plate</th><th>Vehicle description</th></tr></thead><tbody>
    {observations.map((observation) => <tr key={`${observation.id}-${observation.observedAt}`} className={onSelect ? "selectable" : ""} onClick={() => onSelect?.(observation)}><td>{formatObservationTime(observation.observedAt)}</td><td><span className={`observation-status ${observation.status.replace(" ", "-")}`}>{observation.status}</span></td><td>{observation.plate ? <span className="registration">{observation.plate}</span> : "—"}</td><td>{observation.vehicleDescription ?? "—"}</td></tr>)}
  </tbody></table></div>;
}
