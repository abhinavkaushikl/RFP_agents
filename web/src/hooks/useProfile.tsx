import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import type { Profile, ProfileListItem } from "@/lib/types";

const STORAGE = "rfp.profile";

interface ProfileContextValue {
  name: string;
  profile: Profile | undefined;
  profiles: ProfileListItem[];
  loading: boolean;
  setName: (name: string) => void;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE);
  } catch {
    return null;
  }
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [chosen, setChosen] = useState<string | null>(readStored);
  const list = useQuery({ queryKey: ["profiles"], queryFn: api.profiles, staleTime: 60_000 });
  const fallback = list.data?.default ?? "default";
  const known = list.data?.profiles.some((p) => p.name === chosen);
  const name = chosen && (known || !list.data) ? chosen : fallback;
  const detail = useQuery({ queryKey: ["profile", name], queryFn: () => api.profile(name), staleTime: 60_000 });

  const setName = useCallback((next: string) => {
    setChosen(next);
    try {
      localStorage.setItem(STORAGE, next);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const value = useMemo(
    () => ({ name, profile: detail.data, profiles: list.data?.profiles ?? [], loading: detail.isLoading, setName }),
    [name, detail.data, detail.isLoading, list.data, setName],
  );
  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used inside ProfileProvider");
  return ctx;
}

export function sectionTitle(profile: Profile | undefined, key: string): string {
  return profile?.sections.find((s) => s.key === key)?.title ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
