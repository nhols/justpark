export type Period = "day" | "week" | "month" | "quarter" | "year";
export type OccupancySignal = "minutes" | "days";

export interface Booking {
  id: number;
  start: string;
  end: string;
  status: string;
  title: string;
  bookingType: string;
  driverId: number;
  driverName: string;
  driverEmail: string;
  driverPhone: string | null;
  vehicleId: number;
  registration: string;
  vehicle: string;
  vehicleColour: string | null;
  earnings: number;
  paid: number;
}

export interface Driver {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  company: string;
  profilePhoto: string;
  registeredAt: string;
  bookings: number;
  cancelled: number;
  earnings: number;
  paid: number;
  averageHours: number;
  longestHours: number;
  firstBooking: string | null;
  lastBooking: string | null;
  vehicles: string[];
}

export interface Vehicle {
  id: number;
  registration: string;
  make: string;
  model: string;
  colour: string | null;
  primary: boolean;
  autoPay: boolean;
}

export type SeriesPoint = { date: string; value: number };
export type RollingPoint = { date: string } & Record<string, number | string | null>;

export interface Dashboard {
  schemaVersion: number;
  fetchedAt: string;
  generatedAt: string;
  summary: { bookings: number; cancelled: number; drivers: number };
  bookings: Booking[];
  earnings: {
    total: number;
    taxYear: number;
    bookings: number;
    periods: Record<Period, SeriesPoint[]>;
  };
  occupancy: {
    windows: number[];
    minutes: RollingPoint[];
    days: RollingPoint[];
  };
  drivers: Driver[];
  driverHighlights: {
    repeatRate?: number;
    returningRevenueShare?: number;
    topThreeRevenueShare?: number;
    newThisTaxYear?: number;
    busiestWeekday?: string;
    busiestHour?: string;
    longestStay?: { driver: string; hours: number; date: string };
  };
  vehicles: Vehicle[];
}
