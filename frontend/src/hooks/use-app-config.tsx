"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAllAppConfigs,
  createAppConfig,
  updateAppConfig,
  deleteAppConfig,
  getAppConfig,
} from "@/lib/api/appconfig";
import { useMetaInfo } from "@/components/context/metainfo";
import { getApiKey } from "@/lib/api/util";
import { AppConfig } from "@/lib/types/appconfig";

export const appConfigKeys = {
  all: ["appconfigs"] as const,
  detail: (appName: string) => ["appconfigs", appName] as const,
};

export const useAppConfigs = () => {
  const { activeProject } = useMetaInfo();
  const apiKey = getApiKey(activeProject);

  return useQuery<AppConfig[], Error>({
    queryKey: appConfigKeys.all,
    queryFn: () => getAllAppConfigs(apiKey),
    enabled: !!apiKey,

    // silent refresh settings
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchInterval: 60_000,
    refetchIntervalInBackground: true,

    // SWR
    staleTime: 5 * 60_000,
    gcTime: 15 * 60_000,

    // cache placeholder data
    placeholderData: (prev) => prev,
  });
};

export const useAppConfig = (appName: string) => {
  const { activeProject } = useMetaInfo();
  const apiKey = getApiKey(activeProject);

  return useQuery<AppConfig | null, Error>({
    queryKey: appConfigKeys.detail(appName),
    queryFn: () => getAppConfig(appName, apiKey),
    enabled: !!apiKey && !!appName,
  });
};

type CreateAppConfigParams = {
  app_name: string;
  security_scheme: string;
  security_scheme_overrides?: {
    oauth2?: {
      client_id: string;
      client_secret: string;
    } | null;
  };
};

export const useCreateAppConfig = () => {
  const queryClient = useQueryClient();
  const { activeProject } = useMetaInfo();
  const apiKey = getApiKey(activeProject);

  return useMutation<AppConfig, Error, CreateAppConfigParams>({
    mutationFn: (params) =>
      createAppConfig(
        params.app_name,
        params.security_scheme,
        apiKey,
        params.security_scheme_overrides,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appConfigKeys.all });
    },
  });
};

type UpdateAppConfigParams = {
  app_name: string;
  enabled: boolean;
};

export const useUpdateAppConfig = () => {
  const queryClient = useQueryClient();
  const { activeProject } = useMetaInfo();
  const apiKey = getApiKey(activeProject);

  return useMutation<AppConfig, Error, UpdateAppConfigParams>({
    mutationFn: (params) =>
      updateAppConfig(params.app_name, params.enabled, apiKey),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: appConfigKeys.all });
      // The current page may only use the update of a single data item when updating
      queryClient.invalidateQueries({
        queryKey: appConfigKeys.detail(variables.app_name),
      });
    },
  });
};

export const useDeleteAppConfig = () => {
  const queryClient = useQueryClient();
  const { activeProject } = useMetaInfo();
  const apiKey = getApiKey(activeProject);

  return useMutation<Response, Error, string>({
    mutationFn: (app_name) => deleteAppConfig(app_name, apiKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appConfigKeys.all });
    },
  });
};
