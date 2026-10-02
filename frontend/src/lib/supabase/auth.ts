import type { SupabaseClient } from "@supabase/supabase-js";

export type SignUpOutcome = "signed_in" | "confirmation_required";

export async function startGoogleSignIn(
  client: SupabaseClient,
  redirectTo: string,
): Promise<void> {
  const { error } = await client.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo },
  });
  if (error !== null) throw error;
}

export async function signInWithEmailPassword(
  client: SupabaseClient,
  email: string,
  password: string,
): Promise<void> {
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error !== null) throw error;
}

export async function signUpWithEmailPassword(
  client: SupabaseClient,
  email: string,
  password: string,
  emailRedirectTo: string,
): Promise<SignUpOutcome> {
  const { data, error } = await client.auth.signUp({
    email,
    password,
    options: { emailRedirectTo },
  });
  if (error !== null) throw error;
  return data.session === null ? "confirmation_required" : "signed_in";
}
