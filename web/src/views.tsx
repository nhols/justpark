import { useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { CalendarDays, Clock3, Mail, Phone, Repeat2, Sparkles, UsersRound } from "lucide-react";
import { DataTable, Drawer, Empty, Metric, SearchBox, Segmented, type Column } from "./components";
import { chartDate, dateTime, duration, money, percent, shortDate } from "./format";
import type { Booking, Dashboard, Driver, OccupancySignal, Period, Vehicle } from "./types";

const tooltip = { border: "1px solid var(--line)", borderRadius: 14, background: "var(--panel)", color: "var(--ink)", boxShadow: "var(--shadow)" };

function isSingleDay(start: string, end: string) {
  const first = new Date(start);
  const last = new Date(new Date(end).getTime() - 1);
  return first.getFullYear() === last.getFullYear() && first.getMonth() === last.getMonth() && first.getDate() === last.getDate();
}

export function Bookings({ data }: { data: Dashboard }) {
  const [selected, setSelected] = useState<Booking>();
  const [query, setQuery] = useState("");
  const [cancelled, setCancelled] = useState(false);
  const rows = data.bookings.filter((booking) =>
    (cancelled || booking.status !== "cancelled") &&
    `${booking.driverName} ${booking.registration} ${booking.vehicle}`.toLowerCase().includes(query.toLowerCase()),
  );

  return <>
    <div className="panel calendar-panel">
      <div className="calendar-options"><span>Bookings calendar</span><label className="check"><input type="checkbox" checked={cancelled} onChange={(e) => setCancelled(e.target.checked)} /> Show cancelled</label></div>
      <FullCalendar
        plugins={[timeGridPlugin, dayGridPlugin]}
        initialView={innerWidth < 700 ? "dayGridMonth" : "timeGridWeek"}
        firstDay={1}
        allDaySlot={false}
        nowIndicator
        height="auto"
        slotDuration="01:00:00"
        slotMinTime="00:00:00"
        slotMaxTime="24:00:00"
        headerToolbar={{ left: "prev,next today", center: "title", right: "timeGridWeek,dayGridMonth" }}
        buttonText={{ week: "Week", month: "Month", today: "Today" }}
        events={rows.map((booking) => ({
          id: String(booking.id), start: booking.start, end: booking.end,
          title: `${booking.registration} · ${booking.driverName}`,
          className: booking.status === "cancelled" ? "cancelled" : "",
          extendedProps: {
            registration: booking.registration,
            singleDay: isSingleDay(booking.start, booking.end),
          },
        }))}
        eventContent={({ event, timeText, view }) => view.type === "timeGridWeek" || (view.type === "dayGridMonth" && event.extendedProps.singleDay)
          ? <span className="calendar-registration">{event.extendedProps.registration}</span>
          : <><b>{timeText}</b> {event.title}</>}
        eventClick={({ event }) => setSelected(data.bookings.find((booking) => booking.id === Number(event.id)))}
      />
    </div>
    <div className="panel">
      <div className="panel-title"><div><h2>All bookings</h2><p>{rows.length} records</p></div><SearchBox value={query} onChange={setQuery} placeholder="Driver, registration or vehicle" /></div>
      <DataTable rows={[...rows].reverse()} onSelect={setSelected} columns={bookingColumns} />
    </div>
    {selected && <BookingDetail booking={selected} close={() => setSelected(undefined)} />}
  </>;
}

const bookingColumns: Column<Booking>[] = [
  { key: "start", label: "Starts", render: (row) => dateTime(row.start) },
  { key: "driverName", label: "Driver" },
  { key: "registration", label: "Registration", render: (row) => <span className="registration">{row.registration}</span> },
  { key: "vehicle", label: "Vehicle" },
  { key: "earnings", label: "Earnings", render: (row) => money(row.earnings) },
  { key: "status", label: "Status", render: (row) => <span className={`status ${row.status}`}>{row.status}</span> },
];

function BookingDetail({ booking, close }: { booking: Booking; close: () => void }) {
  return <Drawer title={booking.registration} close={close}>
    <div className="drawer-hero"><span className="status confirmed">{booking.status}</span><strong>{money(booking.earnings)}</strong><small>your earnings</small></div>
    <dl className="details">
      <div><dt><CalendarDays size={16} /> Starts</dt><dd>{dateTime(booking.start)}</dd></div>
      <div><dt><Clock3 size={16} /> Ends</dt><dd>{dateTime(booking.end)}</dd></div>
      <div><dt>Driver</dt><dd>{booking.driverName}</dd></div>
      <div><dt><Mail size={16} /> Email</dt><dd><a href={`mailto:${booking.driverEmail}`}>{booking.driverEmail}</a></dd></div>
      <div><dt><Phone size={16} /> Phone</dt><dd>{booking.driverPhone || "—"}</dd></div>
      <div><dt>Vehicle</dt><dd>{booking.vehicle} · {booking.vehicleColour || "colour unknown"}</dd></div>
      <div><dt>Driver paid</dt><dd>{money(booking.paid)}</dd></div>
    </dl>
  </Drawer>;
}

export function Earnings({ data }: { data: Dashboard }) {
  const [period, setPeriod] = useState<Period>("week");
  const series = data.earnings.periods[period];
  return <>
    <div className="metrics three"><Metric label="All-time earnings" value={money(data.earnings.total)} /><Metric label="This tax year" value={money(data.earnings.taxYear)} note="Since 6 April" /><Metric label="Paid bookings" value={data.earnings.bookings.toLocaleString()} /></div>
    <div className="panel chart-panel">
      <div className="panel-title"><div><h2>Earnings over time</h2><p>Net space-owner earnings</p></div><Segmented options={["day", "week", "month", "quarter", "year"] as Period[]} value={period} onChange={setPeriod} format={(value) => value[0].toUpperCase() + value.slice(1)} /></div>
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={series} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="date" tickFormatter={(v) => chartDate(v, period === "year")} axisLine={false} tickLine={false} minTickGap={30} /><YAxis tickFormatter={(v) => `£${v}`} axisLine={false} tickLine={false} width={52} />
          <Tooltip formatter={(value) => money(Number(value))} labelFormatter={(v) => shortDate(String(v))} contentStyle={tooltip} /><Bar dataKey="value" fill="var(--green)" radius={[6, 6, 2, 2]} maxBarSize={52} />
        </BarChart>
      </ResponsiveContainer>
    </div>
    <div className="panel"><DataTable rows={[...series].reverse()} columns={[{ key: "date", label: "Period", render: (r) => shortDate(r.date) }, { key: "value", label: "Earnings", render: (r) => money(r.value) }]} /></div>
  </>;
}

export function Occupancy({ data }: { data: Dashboard }) {
  const [signal, setSignal] = useState<OccupancySignal>("minutes");
  const [windows, setWindows] = useState([7, 30]);
  const colours = ["#2d6c5b", "#d99662", "#6b78a8", "#a65d71"];
  const toggle = (window: number) => setWindows((current) => current.includes(window) ? current.filter((v) => v !== window) : [...current, window].sort((a, b) => a - b));
  return <>
    <div className="panel chart-panel">
      <div className="panel-title occupancy-controls">
        <Segmented options={["minutes", "days"] as OccupancySignal[]} value={signal} onChange={setSignal} format={(v) => v === "minutes" ? "By minute" : "By day"} />
        <div className="window-pills">{data.occupancy.windows.map((window) => <button className={windows.includes(window) ? "active" : ""} onClick={() => toggle(window)} key={window}>{window} days</button>)}</div>
      </div>
      {!windows.length ? <Empty>Select at least one window.</Empty> : <ResponsiveContainer width="100%" height={430}>
        <LineChart data={data.occupancy[signal]} margin={{ top: 24, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="date" tickFormatter={(v) => chartDate(v)} axisLine={false} tickLine={false} minTickGap={44} /><YAxis domain={[0, 1]} tickFormatter={(v) => percent(v)} axisLine={false} tickLine={false} width={48} />
          <Tooltip formatter={(value, name) => [percent(Number(value)), `${name} day window`]} labelFormatter={(v) => shortDate(String(v))} contentStyle={tooltip} /><Legend formatter={(v) => `${v} day window`} />
          {windows.map((window, i) => <Line key={window} dataKey={String(window)} connectNulls type="monotone" stroke={colours[i]} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />)}
        </LineChart>
      </ResponsiveContainer>}
    </div>
  </>;
}

export function Drivers({ data }: { data: Dashboard }) {
  const [selected, setSelected] = useState<Driver>();
  const [query, setQuery] = useState("");
  const rows = data.drivers.filter((driver) => `${driver.name} ${driver.email} ${driver.vehicles}`.toLowerCase().includes(query.toLowerCase()));
  const h = data.driverHighlights;
  return <>
    <div className="highlights">
      <article className="highlight feature"><Repeat2 /><span>Repeat drivers</span><strong>{percent(h.repeatRate)}</strong><small>{percent(h.returningRevenueShare)} of revenue comes from them</small></article>
      <article className="highlight"><Sparkles /><span>Longest stay</span><strong>{duration(h.longestStay?.hours || 0)}</strong><small>{h.longestStay?.driver || "—"}</small></article>
      <article className="highlight"><UsersRound /><span>Top three share</span><strong>{percent(h.topThreeRevenueShare)}</strong><small>of all earnings</small></article>
      <article className="highlight"><Clock3 /><span>Favourite arrival</span><strong>{h.busiestHour || "—"}</strong><small>{h.busiestWeekday || "—"}</small></article>
    </div>
    <div className="panel">
      <div className="panel-title"><div><h2>Driver leaderboard</h2><p>Ranked by your earnings</p></div><SearchBox value={query} onChange={setQuery} placeholder="Search drivers" /></div>
      <DataTable rows={rows} columns={driverColumns} onSelect={setSelected} />
    </div>
    {selected && <DriverDetail driver={selected} bookings={data.bookings.filter((booking) => booking.driverId === selected.id)} close={() => setSelected(undefined)} />}
  </>;
}

const driverColumns: Column<Driver>[] = [
  { key: "name", label: "Driver", render: (r) => <div className="person"><span>{r.name.slice(0, 1)}</span><div><strong>{r.name}</strong><small>{r.email}</small></div></div> },
  { key: "vehicles", label: "Vehicle", render: (r) => r.vehicles.map((v) => <span className="registration" key={v}>{v}</span>) },
  { key: "bookings", label: "Bookings" },
  { key: "cancelled", label: "Cancelled" },
  { key: "averageHours", label: "Average stay", render: (r) => duration(r.averageHours) },
  { key: "earnings", label: "Earnings", render: (r) => <strong>{money(r.earnings)}</strong> },
];

function DriverDetail({ driver, bookings, close }: { driver: Driver; bookings: Booking[]; close: () => void }) {
  const history = driverHistory(bookings);
  return <Drawer title={driver.name} close={close}>
    <div className="profile"><div className="avatar">{driver.name.slice(0, 1)}</div><div><a href={`mailto:${driver.email}`}>{driver.email}</a><span>{driver.phone || "No phone number"}</span></div></div>
    <div className="mini-metrics"><Metric label="Earnings" value={money(driver.earnings)} /><Metric label="Bookings" value={driver.bookings} /><Metric label="Longest stay" value={duration(driver.longestHours)} /><Metric label="Average stay" value={duration(driver.averageHours)} /></div>
    <section className="driver-history"><h3>Bookings over time</h3>{history.length ? <ResponsiveContainer width="100%" height={170}>
      <BarChart data={history} margin={{ top: 12, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="date" tickFormatter={(v) => chartDate(v, true)} axisLine={false} tickLine={false} minTickGap={28} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} width={24} />
        <Tooltip formatter={(value) => [Number(value), "Bookings"]} labelFormatter={(v) => chartDate(String(v), true)} contentStyle={tooltip} /><Bar dataKey="bookings" fill="var(--green)" radius={[5, 5, 2, 2]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer> : <p>No completed bookings.</p>}</section>
    <dl className="details"><div><dt>Vehicles</dt><dd>{driver.vehicles.join(", ")}</dd></div><div><dt>First booking</dt><dd>{driver.firstBooking ? shortDate(driver.firstBooking) : "—"}</dd></div><div><dt>Latest booking</dt><dd>{driver.lastBooking ? shortDate(driver.lastBooking) : "—"}</dd></div><div><dt>Registered</dt><dd>{shortDate(driver.registeredAt)}</dd></div></dl>
  </Drawer>;
}

function driverHistory(bookings: Booking[]) {
  const months = new Map<string, number>();
  bookings.filter((booking) => booking.status !== "cancelled").forEach((booking) => {
    const date = `${booking.start.slice(0, 7)}-01`;
    months.set(date, (months.get(date) || 0) + 1);
  });
  return [...months].sort(([a], [b]) => a.localeCompare(b)).map(([date, count]) => ({ date, bookings: count }));
}

export function RawData({ data }: { data: Dashboard }) {
  const [table, setTable] = useState<"bookings" | "drivers" | "vehicles">("bookings");
  const [query, setQuery] = useState("");
  const match = (row: object) => JSON.stringify(row).toLowerCase().includes(query.toLowerCase());
  return <>
    <div className="panel"><div className="panel-title"><Segmented options={["bookings", "drivers", "vehicles"] as const} value={table} onChange={(value) => { setTable(value); setQuery(""); }} format={(v) => v[0].toUpperCase() + v.slice(1)} /><SearchBox value={query} onChange={setQuery} /></div>
      {table === "bookings" && <DataTable rows={data.bookings.filter(match)} columns={bookingColumns} />}
      {table === "drivers" && <DataTable rows={data.drivers.filter(match)} columns={driverColumns} />}
      {table === "vehicles" && <DataTable rows={data.vehicles.filter(match)} columns={vehicleColumns} />}
    </div>
  </>;
}

const vehicleColumns: Column<Vehicle>[] = [
  { key: "registration", label: "Registration", render: (r) => <span className="registration">{r.registration}</span> },
  { key: "make", label: "Make" }, { key: "model", label: "Model" }, { key: "colour", label: "Colour" },
  { key: "autoPay", label: "Auto pay", render: (r) => r.autoPay ? "Yes" : "No" },
];
