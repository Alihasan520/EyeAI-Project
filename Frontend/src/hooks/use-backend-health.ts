import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { useSettingsStore } from "../features/settings/settings-store";
import { getHealth } from "../lib/api";

export function useBackendHealth(enabled = true) {
  const apiBaseUrl = useSettingsStore((state) => state.apiBaseUrl);
  const setBackendState = useSettingsStore((state) => state.setBackendState);

  const query = useQuery({
    queryKey: ["backend-health", apiBaseUrl],
    queryFn: getHealth,
    enabled,
    refetchInterval: 30_000,
    retry: 1,
  });

  useEffect(() => {
    if (query.isLoading) {
      setBackendState("warming");
    } else if (query.isSuccess) {
      setBackendState("online");
    } else if (query.isError) {
      setBackendState("offline");
    }
  }, [query.isError, query.isLoading, query.isSuccess, setBackendState]);

  return query;
}
