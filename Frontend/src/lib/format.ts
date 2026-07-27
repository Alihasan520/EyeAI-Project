import type { Language } from "./types";

export function formatDate(value: string | Date, language: Language): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat(language === "ar" ? "ar-EG" : "en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatNumber(value: number, language: Language): string {
  return new Intl.NumberFormat(language === "ar" ? "ar-EG" : "en-US").format(value);
}

export function normalizeUrl(value: string): string {
  const trimmed = value.trim();
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}
