"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getCurrentUserProfile,
  getReadableError,
  type CurrentUserProfileResponse,
} from "@/lib/api/challenges";
import { createClient } from "@/lib/supabase/client";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

import { ProfileError, ProfileLoading, ProfileSummary } from "./profile-summary";

export function ProfileDashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState<CurrentUserProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (getSupabasePublicConfig() === null) {
      queueMicrotask(() => setError("Authentication is not configured in this environment."));
      return;
    }
    let active = true;
    const supabase = createClient();
    void supabase.auth.getSession()
      .then(async ({ data }) => {
        if (!active) return;
        if (data.session === null) {
          router.replace("/login?next=/profile");
          return;
        }
        try {
          const result = await getCurrentUserProfile(data.session.access_token);
          if (active) setProfile(result);
        } catch (loadError) {
          if (active) setError(getReadableError(loadError));
        }
      })
      .catch(() => {
        if (active) setError("We couldn’t restore your authenticated session.");
      });
    return () => { active = false; };
  }, [loadAttempt, router]);

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/");
    router.refresh();
  }

  if (error !== null) {
    return (
      <ProfileError
        message={error}
        onRetry={() => {
          setError(null);
          setProfile(null);
          setLoadAttempt((value) => value + 1);
        }}
      />
    );
  }
  if (profile === null) return <ProfileLoading />;
  return <ProfileSummary profile={profile} onSignOut={() => void signOut()} />;
}
