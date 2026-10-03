import { useEffect, useLayoutEffect, useMemo, useRef, useState, type UIEvent } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useRenderStages } from "./components";
import { addDays, startOfWeek } from "./ContinuousWeekCalendar";
import type { Booking } from "./types";

const VISIBLE_WEEKS = 6;
// Only a window of weeks is rendered; it slides along as you scroll so the grid feels endless.
const WINDOW_WEEKS = 30;
const SHIFT_WEEKS = 10;
const EDGE_WEEKS = 6;
// Last measured grid height, so the view opens at the right size before it can measure again.
let rememberedContentHeight = 436;

function isSingleDay(start: string, end: string) {
  const first = new Date(start);
  const last = new Date(new Date(end).getTime() - 1);
  return first.getFullYear() === last.getFullYear() && first.getMonth() === last.getMonth() && first.getDate() === last.getDate();
}

function monthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

// FullCalendar's day grid laid out as a run of weeks, scrolled vertically month to month.
export function ContinuousMonthCalendar({ bookings, firstBookingIds, initialDate, onSelect, onWeek }: {
  bookings: Booking[];
  firstBookingIds: ReadonlySet<number>;
  initialDate: Date;
  onSelect: (booking: Booking) => void;
  onWeek: (date: Date) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const calendar = useRef<FullCalendar>(null);
  const scrollTick = useRef<number | undefined>(undefined);
  const programmaticScroll = useRef<number | undefined>(undefined);
  const windowStart = useRef(addDays(startOfWeek(monthStart(initialDate)), -SHIFT_WEEKS * 7));
  const [focusedMonth, setFocusedMonth] = useState(() => monthStart(initialDate));
  const [contentHeight, setContentHeight] = useState(rememberedContentHeight);
  const anchor = useRef<{ date: string; offset: number }>(undefined);
  // 0: toolbar and an empty frame, 1: the grid, 2: the bookings.
  const stage = useRenderStages(2);
  const loaded = useRef(false);
  loaded.current = stage >= 2;

  const events = useMemo(() => bookings.map((booking) => ({
    id: String(booking.id), start: booking.start, end: booking.end,
    title: `${booking.registration} · ${booking.driverName}`,
    className: [booking.status === "cancelled" ? "cancelled" : "", firstBookingIds.has(booking.id) ? "first-booking" : ""].filter(Boolean).join(" "),
    extendedProps: { registration: booking.registration, singleDay: isSingleDay(booking.start, booking.end), firstBooking: firstBookingIds.has(booking.id) },
  })), [bookings, firstBookingIds]);

  const scroller = () => container.current?.querySelector<HTMLElement>(".fc-daygrid-body")?.closest<HTMLElement>(".fc-scroller") ?? undefined;
  const rows = () => [...container.current?.querySelectorAll<HTMLElement>(".fc-daygrid-body tr[role=row]") ?? []];

  // Remembers the top visible week so it can be held in place when the grid re-renders.
  const captureAnchor = () => {
    const element = scroller();
    if (!element) return;
    const top = element.getBoundingClientRect().top;
    const row = rows().find((item) => item.getBoundingClientRect().bottom > top);
    const date = row?.querySelector<HTMLElement>("td[data-date]")?.dataset.date;
    anchor.current = date ? { date, offset: row!.getBoundingClientRect().top - top } : undefined;
  };

  const restoreAnchor = () => {
    const element = scroller();
    const saved = anchor.current;
    const row = saved && container.current?.querySelector(`.fc-daygrid-body td[data-date="${saved.date}"]`)?.closest("tr");
    if (element && saved && row) element.scrollTop += row.getBoundingClientRect().top - element.getBoundingClientRect().top - saved.offset;
  };

  // Moves the rendered window by whole weeks, keeping whatever is on screen in place.
  const shiftWindow = (weeks: number) => {
    const api = calendar.current?.getApi();
    if (!api) return;
    captureAnchor();
    windowStart.current = addDays(windowStart.current, weeks * 7);
    api.gotoDate(windowStart.current);
    restoreAnchor();
  };

  const keepAwayFromEdges = () => {
    const element = scroller();
    if (!element || !loaded.current || programmaticScroll.current !== undefined) return;
    const top = element.getBoundingClientRect().top;
    const all = rows();
    const first = all.findIndex((row) => row.getBoundingClientRect().bottom > top);
    const last = all.findIndex((row) => row.getBoundingClientRect().bottom >= top + element.clientHeight);
    if (first < EDGE_WEEKS) shiftWindow(-SHIFT_WEEKS);
    else if (last === -1 || last > all.length - 1 - EDGE_WEEKS) shiftWindow(SHIFT_WEEKS);
  };

  const scrollToMonth = (date: Date, behavior: ScrollBehavior = "auto") => {
    const target = startOfWeek(monthStart(date));
    const weeksIn = Math.round((target.getTime() - windowStart.current.getTime()) / (7 * 86_400_000));
    if (weeksIn < EDGE_WEEKS + 1 || weeksIn > WINDOW_WEEKS - EDGE_WEEKS - VISIBLE_WEEKS - 1) shiftWindow(weeksIn - SHIFT_WEEKS);
    const element = scroller();
    const row = container.current?.querySelector(`.fc-daygrid-body td[data-date="${dateKey(monthStart(date))}"]`)?.closest("tr");
    if (!element || !row) return;
    // Hold off sliding the window until a smooth scroll has settled.
    if (programmaticScroll.current !== undefined) clearTimeout(programmaticScroll.current);
    programmaticScroll.current = window.setTimeout(() => {
      programmaticScroll.current = undefined;
      keepAwayFromEdges();
    }, behavior === "smooth" ? 700 : 0);
    const top = row.getBoundingClientRect().top - element.getBoundingClientRect().top + element.scrollTop;
    anchor.current = { date: row.querySelector<HTMLElement>("td[data-date]")!.dataset.date!, offset: 0 };
    element.scrollTo({ top, behavior });
  };

  const updateFocus = () => {
    const element = scroller();
    if (!element) return;
    const middle = element.getBoundingClientRect().top + element.clientHeight / 2;
    const row = rows().find((item) => item.getBoundingClientRect().bottom > middle);
    const thursday = row?.querySelectorAll<HTMLElement>("td[data-date]")[3]?.dataset.date;
    if (!thursday) return;
    const [year, month] = thursday.split("-").map(Number);
    setFocusedMonth((current) => current.getFullYear() === year && current.getMonth() === month - 1 ? current : new Date(year, month - 1, 1));
  };

  // Once the grid exists, size the scroll area to six ordinary weeks and open on the requested month.
  useLayoutEffect(() => {
    if (stage !== 1) return;
    const header = container.current?.querySelector<HTMLElement>(".fc-col-header");
    const heights = rows().map((row) => row.getBoundingClientRect().height);
    if (header && heights.length) {
      rememberedContentHeight = header.getBoundingClientRect().height + Math.min(...heights) * VISIBLE_WEEKS + 2;
      setContentHeight(rememberedContentHeight);
    }
    scrollToMonth(initialDate);
  }, [stage === 1]);

  // Bookings change row heights, so keep the same week at the top when they are drawn.
  useLayoutEffect(() => {
    if (stage >= 2) restoreAnchor();
  }, [stage >= 2, bookings]);

  // Scroll events don't bubble, so they are caught on the way down; FullCalendar can swap its scroller element.
  const onScroll = (event: UIEvent<HTMLDivElement>) => {
    if (event.target !== scroller() || scrollTick.current !== undefined) return;
    scrollTick.current = requestAnimationFrame(() => {
      scrollTick.current = undefined;
      // FullCalendar resets the scroll position while it lays out, so hold the requested month until loaded.
      if (!loaded.current) restoreAnchor();
      else {
        keepAwayFromEdges();
        captureAnchor();
      }
      updateFocus();
    });
  };

  useEffect(() => () => {
    if (scrollTick.current !== undefined) cancelAnimationFrame(scrollTick.current);
    scrollTick.current = undefined;
    if (programmaticScroll.current !== undefined) clearTimeout(programmaticScroll.current);
    programmaticScroll.current = undefined;
  }, []);

  const sameMonth = (date: Date) => date.getFullYear() === focusedMonth.getFullYear() && date.getMonth() === focusedMonth.getMonth();
  const today = new Date();

  return <div className="month-calendar" ref={container} onScrollCapture={onScroll}>
    <div className="continuous-toolbar">
      <div><span className="toolbar-group"><button className="toolbar-icon" aria-label="Previous month" onClick={() => scrollToMonth(new Date(focusedMonth.getFullYear(), focusedMonth.getMonth() - 1, 1), "smooth")}><ChevronUp size={18} /></button><button className="toolbar-icon" aria-label="Next month" onClick={() => scrollToMonth(new Date(focusedMonth.getFullYear(), focusedMonth.getMonth() + 1, 1), "smooth")}><ChevronDown size={18} /></button></span><button onClick={() => scrollToMonth(today, "smooth")}>Today</button></div>
      <h2>{focusedMonth.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</h2>
      <div>{stage < 2 && <span className="toolbar-spinner" role="status" aria-label="Loading bookings" />}<span className="toolbar-group"><button onClick={() => onWeek(sameMonth(today) ? today : focusedMonth)}>Week</button><button className="active">Month</button></span></div>
    </div>
    {stage < 1 ? <div className="calendar-placeholder" style={{ height: contentHeight }} /> : <FullCalendar
      ref={calendar}
      plugins={[dayGridPlugin]}
      initialView="continuousMonth"
      views={{ continuousMonth: { type: "dayGrid", duration: { weeks: WINDOW_WEEKS } } }}
      initialDate={windowStart.current}
      firstDay={1}
      headerToolbar={false}
      dayHeaderFormat={{ weekday: "short" }}
      contentHeight={contentHeight}
      events={stage >= 2 ? events : []}
      dayCellContent={({ date }) => ({ html: String(date.getDate()) })}
      dayCellClassNames={({ date }) => sameMonth(date) ? [] : ["fc-day-other"]}
      eventContent={({ event, timeText }) => {
        // Plain DOM content renders much faster than a React portal per event.
        if (event.extendedProps.singleDay) {
          const registration = document.createElement("span");
          registration.className = "calendar-registration";
          registration.textContent = event.extendedProps.registration;
          return { domNodes: [registration] };
        }
        const time = document.createElement("b");
        time.textContent = timeText;
        return { domNodes: [time, document.createTextNode(` ${event.title}`)] };
      }}
      eventClick={({ event }) => {
        const booking = bookings.find((item) => item.id === Number(event.id));
        if (booking) onSelect(booking);
      }}
      eventDidMount={({ event, el }) => {
        if (event.extendedProps.firstBooking) el.setAttribute("title", "First booking for this driver");
      }}
    />}
  </div>;
}
