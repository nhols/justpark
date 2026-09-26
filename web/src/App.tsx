import { useEffect, useRef, useState } from "react";
import { BarChart3, CalendarDays, Camera, CarFront, Database, Monitor, Moon, RefreshCw, Sun, UsersRound, X } from "lucide-react";
import { Bookings, Drivers, Earnings, Occupancy, RawData } from "./views";
import { Observations } from "./ObservationTimeline";
import { relative } from "./format";
import type { Dashboard } from "./types";

const views = {
  bookings: { label: "Bookings", icon: CalendarDays, component: Bookings },
  observations: { label: "Observations", icon: Camera, component: Observations },
  earnings: { label: "Earnings", icon: BarChart3, component: Earnings },
  occupancy: { label: "Occupancy", icon: CarFront, component: Occupancy },
  drivers: { label: "Drivers", icon: UsersRound, component: Drivers },
  data: { label: "Data", icon: Database, component: RawData },
};
type View = keyof typeof views;
type Theme = "system" | "light" | "dark";
const appIcon = `${import.meta.env.BASE_URL}icons/icon-192.png`;
const dataUrl = `${import.meta.env.BASE_URL}${import.meta.env.DEV ? "dashboard.json" : "api/dashboard"}`;
const updateCheckInterval = 5 * 60_000;

function initialView(): View {
  const hash = location.hash.slice(1);
  return hash in views ? hash as View : "bookings";
}

export default function App() {
  const [data, setData] = useState<Dashboard>();
  const [error, setError] = useState("");
  const [view, setView] = useState<View>(initialView);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("theme") as Theme) || "system");
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const etag = useRef<string | null>(null);
  const [, tick] = useState(0);

  const load = () => {
    setError("");
    fetch(dataUrl, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`Data request failed (${response.status})`);
        etag.current = response.headers.get("ETag");
        return response.json();
      })
      .then((payload: Dashboard) => {
        if (payload.schemaVersion !== 2) throw new Error("Unsupported dashboard data");
        setData(payload);
        setUpdateAvailable(false);
      })
      .catch((reason) => setError(reason.message));
  };

  useEffect(load, []);
  useEffect(() => {
    const check = () => {
      if (document.visibilityState !== "visible" || !etag.current) return;
      fetch(dataUrl, { method: "HEAD", cache: "no-store" })
        .then((response) => {
          const latest = response.ok && response.headers.get("ETag");
          if (latest && latest !== etag.current) setUpdateAvailable(true);
        })
        .catch(() => {});
    };
    const timer = setInterval(check, updateCheckInterval);
    document.addEventListener("visibilitychange", check);
    addEventListener("focus", check);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
      removeEventListener("focus", check);
    };
  }, []);
  useEffect(() => { const timer = setInterval(() => tick((value) => value + 1), 60_000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
      localStorage.setItem("theme", theme);
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  useEffect(() => {
    const onHashChange = () => {
      const next = location.hash.slice(1);
      if (next in views) setView(next as View);
      scrollTo({ top: 0, behavior: "smooth" });
    };
    addEventListener("hashchange", onHashChange);
    return () => removeEventListener("hashchange", onHashChange);
  }, []);

  if (!data) return <main className="centre-state"><img className="brand-mark" src={appIcon} alt="" />{error ? <><h1>Couldn’t load the dashboard</h1><p>{error}</p><button onClick={load}>Try again</button></> : <><div className="loader" /><p>Preparing your space…</p></>}</main>;

  const Page = views[view].component;
  return <div className="shell">
    <header className="topbar">
      <a className="brand" href="#bookings"><img className="brand-mark" src={appIcon} alt="" /><span>JustPark Earnings<small>Private dashboard</small></span></a>
      <div className="topbar-actions"><ThemePicker value={theme} onChange={setTheme} /><div className={updateAvailable ? "freshness stale" : "freshness"}><span /><div><strong>Data updated {relative(data.fetchedAt)}</strong><small>{data.summary.bookings} bookings · {data.summary.drivers} drivers</small></div><button className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={17} /></button></div></div>
    </header>
    <nav>{Object.entries(views).map(([key, item]) => <button key={key} className={view === key ? "active" : ""} onClick={() => { setView(key as View); location.hash = key; scrollTo({ top: 0, behavior: "smooth" }); }}><item.icon size={18} /><span>{item.label}</span></button>)}</nav>
    {updateAvailable && <div className="update-toast" role="status"><RefreshCw size={16} /><span>New data is available</span><button className="update-refresh" onClick={load}>Refresh</button><button className="icon-button" onClick={() => setUpdateAvailable(false)} aria-label="Dismiss"><X size={16} /></button></div>}
    <main><Page data={data} /></main>
    <footer>Private dashboard · Europe/London</footer>
  </div>;
}

function ThemePicker({ value, onChange }: { value: Theme; onChange: (theme: Theme) => void }) {
  const options = [{ value: "system", label: "System", icon: Monitor }, { value: "light", label: "Light", icon: Sun }, { value: "dark", label: "Dark", icon: Moon }] as const;
  return <div className="theme-toggle" role="group" aria-label="Theme">{options.map((option) => <button key={option.value} className={value === option.value ? "active" : ""} aria-pressed={value === option.value} aria-label={`${option.label} theme`} title={option.label} onClick={() => onChange(option.value)}><option.icon size={16} /></button>)}</div>;
}
