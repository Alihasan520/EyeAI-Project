export const DEFAULT_API_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

export const PREVIEW_MODE_ENABLED =
  import.meta.env.VITE_ENABLE_PREVIEW_MODE !== "false";

export const FRONTEND_VERSION = "0.4.2";
