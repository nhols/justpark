import { useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { Booking } from "./types";

const AXIS_WIDTH = 52;
const HEADER_HEIGHT = 40;
const DEFAULT_HOUR_HEIGHT = 24;
const RANGE_DAYS = 365 * 20;

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfWeek(date: Date) {
  const start = startOfDay(date);
  start.setDate(start.getDate() - (start.getDay() + 6) % 7);
  return start;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function dayDistance(first: Date, second: Date) {
  const a = Date.UTC(first.getFullYear(), first.getMonth(), first.getDate());
  const b = Date.UTC(second.getFullYear(), second.getMonth(), second.getDate());
  return Math.round((b - a) / 86_400_000);
}

function weekTitle(start: Date) {
  const end = addDays(start, 6);
  const startMonth = start.toLocaleDateString("en-GB", { month: "short" });
  const endMonth = end.toLocaleDateString("en-GB", { month: "short" });
  if (start.getFullYear() !== end.getFullYear()) return `${startMonth} ${start.getDate()}, ${start.getFullYear()} – ${endMonth} ${end.getDate()}, ${end.getFullYear()}`;
  if (start.getMonth() === end.getMonth()) return `${startMonth} ${start.getDate()} – ${end.getDate()}, ${end.getFullYear()}`;
  return `${startMonth} ${start.getDate()} – ${endMonth} ${end.getDate()}, ${end.getFullYear()}`;
}

type Segment = { booking: Booking; day: number; startMinutes: number; endMinutes: number };

export function ContinuousWeekCalendar({ bookings, initialDate, onSelect, onMonth }: {
  bookings: Booking[];
  initialDate: Date;
  onSelect: (booking: Booking) => void;
  onMonth: (date: Date) => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const momentum = useRef<number | undefined>(undefined);
  const drag = useRef<{ pointerId: number; x: number; scroll: number; lastX: number; lastTime: number; velocity: number; active: boolean } | undefined>(undefined);
  const suppressClick = useRef(false);
  const scrollTick = useRef<number | undefined>(undefined);
  const dayWidthRef = useRef(140);
  const [dayWidth, setDayWidth] = useState(140);
  const [axisWidth, setAxisWidth] = useState(AXIS_WIDTH);
  const [hourHeight, setHourHeight] = useState(DEFAULT_HOUR_HEIGHT);
  const rangeStart = useMemo(() => addDays(startOfWeek(new Date()), -RANGE_DAYS / 2), []);
  const [visibleDay, setVisibleDay] = useState(() => dayDistance(rangeStart, startOfWeek(initialDate)));

  const segments = useMemo(() => bookings.flatMap((booking) => {
    const start = new Date(booking.start);
    const end = new Date(booking.end);
    const result: Segment[] = [];
    for (let day = startOfDay(start); day < end; day = addDays(day, 1)) {
      const next = addDays(day, 1);
      const segmentStart = start > day ? start : day;
      const segmentEnd = end < next ? end : next;
      result.push({
        booking,
        day: dayDistance(rangeStart, day),
        startMinutes: (segmentStart.getTime() - day.getTime()) / 60_000,
        endMinutes: (segmentEnd.getTime() - day.getTime()) / 60_000,
      });
    }
    return result;
  }), [bookings, rangeStart]);

  const stopMomentum = () => {
    if (momentum.current !== undefined) cancelAnimationFrame(momentum.current);
    momentum.current = undefined;
  };

  const fling = (velocity: number) => {
    stopMomentum();
    if (Math.abs(velocity) < .05) return;
    let speed = Math.max(-2.2, Math.min(2.2, velocity));
    let previous = performance.now();
    const step = (now: number) => {
      const elapsed = Math.min(32, now - previous);
      previous = now;
      if (viewport.current) viewport.current.scrollLeft += speed * elapsed;
      speed *= Math.pow(.92, elapsed / 16);
      if (Math.abs(speed) < .02) return void (momentum.current = undefined);
      momentum.current = requestAnimationFrame(step);
    };
    momentum.current = requestAnimationFrame(step);
  };

  const scrollToDate = (date: Date, behavior: ScrollBehavior = "auto") => {
    viewport.current?.scrollTo({ left: dayDistance(rangeStart, startOfWeek(date)) * dayWidth, behavior });
  };

  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const measure = () => {
      const firstVisible = element.scrollLeft ? element.scrollLeft / dayWidthRef.current : dayDistance(rangeStart, startOfWeek(initialDate));
      const nextAxisWidth = element.clientWidth < 600 ? 32 : AXIS_WIDTH;
      const width = (element.clientWidth - nextAxisWidth) / 7;
      const availableHeight = window.innerHeight - element.getBoundingClientRect().top - 20;
      const fittedHourHeight = Math.max(8, Math.min(32, (availableHeight - HEADER_HEIGHT) / 24));
      dayWidthRef.current = width;
      setDayWidth(width);
      setAxisWidth(nextAxisWidth);
      setHourHeight(fittedHourHeight);
      requestAnimationFrame(() => { element.scrollLeft = firstVisible * width; });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => {
      observer.disconnect();
      stopMomentum();
      if (scrollTick.current !== undefined) cancelAnimationFrame(scrollTick.current);
    };
  }, []);

  const headers = Array.from({ length: 11 }, (_, offset) => {
    const index = Math.max(0, Math.min(RANGE_DAYS - 1, visibleDay - 2 + offset));
    return { index, date: addDays(rangeStart, index) };
  });
  const visibleStart = addDays(rangeStart, visibleDay);
  const todayIndex = dayDistance(rangeStart, startOfDay(new Date()));
  const now = new Date();
  const nowTop = HEADER_HEIGHT + (now.getHours() * 60 + now.getMinutes()) / 60 * hourHeight;

  const eventGutter = dayWidth < 70 ? 2 : 4;

  return <div className="continuous-calendar" style={{ "--calendar-axis": `${axisWidth}px`, "--calendar-header": `${HEADER_HEIGHT}px`, "--calendar-hour": `${hourHeight}px` } as CSSProperties}>
    <div className="continuous-toolbar">
      <div><button aria-label="Previous week" onClick={() => viewport.current?.scrollBy({ left: -dayWidth * 7, behavior: "smooth" })}>‹</button><button aria-label="Next week" onClick={() => viewport.current?.scrollBy({ left: dayWidth * 7, behavior: "smooth" })}>›</button><button onClick={() => scrollToDate(new Date(), "smooth")}>Today</button></div>
      <h2>{weekTitle(visibleStart)}</h2>
      <div><button className="active">Week</button><button onClick={() => onMonth(visibleStart)}>Month</button></div>
    </div>
    <div
      className="continuous-viewport"
      ref={viewport}
      onScroll={(event) => {
        if (scrollTick.current !== undefined) return;
        const element = event.currentTarget;
        scrollTick.current = requestAnimationFrame(() => {
          setVisibleDay(Math.round(element.scrollLeft / dayWidth));
          scrollTick.current = undefined;
        });
      }}
      onPointerDown={(event) => {
        if (event.pointerType !== "mouse" || event.button !== 0) return;
        stopMomentum();
        drag.current = { pointerId: event.pointerId, x: event.clientX, scroll: event.currentTarget.scrollLeft, lastX: event.clientX, lastTime: performance.now(), velocity: 0, active: false };
      }}
      onPointerMove={(event) => {
        const state = drag.current;
        if (!state || state.pointerId !== event.pointerId) return;
        const distance = state.x - event.clientX;
        if (!state.active && Math.abs(distance) < 6) return;
        if (!state.active) {
          state.active = true;
          event.currentTarget.setPointerCapture(event.pointerId);
          event.currentTarget.classList.add("dragging");
        }
        const now = performance.now();
        const elapsed = now - state.lastTime;
        if (elapsed > 0) state.velocity = state.velocity * .65 - (event.clientX - state.lastX) / elapsed * .35;
        state.lastX = event.clientX;
        state.lastTime = now;
        event.currentTarget.scrollLeft = state.scroll + distance;
      }}
      onPointerUp={(event) => {
        const state = drag.current;
        if (!state || state.pointerId !== event.pointerId) return;
        drag.current = undefined;
        event.currentTarget.classList.remove("dragging");
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        if (state.active) {
          suppressClick.current = true;
          setTimeout(() => { suppressClick.current = false; }, 0);
          fling(performance.now() - state.lastTime > 80 ? 0 : state.velocity);
        }
      }}
      onPointerCancel={(event) => {
        drag.current = undefined;
        event.currentTarget.classList.remove("dragging");
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      }}
    >
      <div className="continuous-content" style={{ width: axisWidth + RANGE_DAYS * dayWidth, height: HEADER_HEIGHT + hourHeight * 24 }}>
        {Array.from({ length: 25 }, (_, hour) => <div className="continuous-horizontal-line" key={`line-${hour}`} style={{ top: HEADER_HEIGHT + hour * hourHeight }} />)}
        {headers.map(({ index }) => <div className="continuous-vertical-line" key={`column-${index}`} style={{ left: axisWidth + index * dayWidth }} />)}
        <div className="continuous-today" style={{ left: axisWidth + todayIndex * dayWidth, width: dayWidth }} />
        {headers.map(({ index, date }) => <div className="continuous-day-header" key={index} style={{ left: axisWidth + index * dayWidth, width: dayWidth }}>{date.toLocaleDateString("en-GB", { weekday: "short" }).toUpperCase()} {date.getMonth() + 1}/{date.getDate()}</div>)}
        <div className="continuous-axis-header" />
        <div className="continuous-axis-body" style={{ height: hourHeight * 24 }}>
          {Array.from({ length: 24 }, (_, hour) => <div className="continuous-hour" key={hour} style={{ top: hour * hourHeight, height: hourHeight }}>{hour === 0 ? "12am" : hour < 12 ? `${hour}am` : hour === 12 ? "12pm" : `${hour - 12}pm`}</div>)}
        </div>
        <div className="continuous-now" style={{ left: axisWidth + todayIndex * dayWidth, top: nowTop, width: dayWidth }} />
        {segments.map((segment, index) => segment.day >= 0 && segment.day < RANGE_DAYS && <button
          className={`continuous-event ${segment.booking.status === "cancelled" ? "cancelled" : ""}`}
          key={`${segment.booking.id}-${index}`}
          style={{ left: axisWidth + segment.day * dayWidth + eventGutter, width: dayWidth - eventGutter * 2, top: HEADER_HEIGHT + segment.startMinutes / 60 * hourHeight, height: Math.max(14, (segment.endMinutes - segment.startMinutes) / 60 * hourHeight) }}
          onClick={() => { if (!suppressClick.current) onSelect(segment.booking); }}
        ><span>{segment.booking.registration}</span></button>)}
      </div>
    </div>
  </div>;
}
