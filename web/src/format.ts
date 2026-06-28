import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

export const money = (value: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);

export const percent = (value = 0) => `${Math.round(value * 100)}%`;
export const duration = (value: number) => {
  let hours = Math.max(0, Math.round(value));
  const weeks = Math.floor(hours / 168);
  hours %= 168;
  const days = Math.floor(hours / 24);
  hours %= 24;
  return `${weeks ? `${weeks}w` : ""}${days ? `${days}d` : ""}${hours ? `${hours}h` : ""}` || "0h";
};
export const relative = (value: string) => formatDistanceToNowStrict(parseISO(value), { addSuffix: true });
export const shortDate = (value: string) => format(parseISO(value), "d MMM yyyy");
export const dateTime = (value: string) => format(parseISO(value), "EEE d MMM, HH:mm");
export const chartDate = (value: string, long = false) => format(parseISO(value), long ? "MMM yyyy" : "d MMM");
