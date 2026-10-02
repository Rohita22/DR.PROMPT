import { describe, expect, it, vi } from "vitest";

import {
  signInWithEmailPassword,
  signUpWithEmailPassword,
  startGoogleSignIn,
} from "./auth";

function clientWithAuth(auth: object) {
  return { auth } as never;
}

describe("Supabase authentication helpers", () => {
  it("starts Google OAuth with the application callback", async () => {
    const signInWithOAuth = vi.fn().mockResolvedValue({ error: null });

    await startGoogleSignIn(
      clientWithAuth({ signInWithOAuth }),
      "http://localhost:3000/auth/callback",
    );

    expect(signInWithOAuth).toHaveBeenCalledWith({
      provider: "google",
      options: { redirectTo: "http://localhost:3000/auth/callback" },
    });
  });

  it("signs in with an email and password", async () => {
    const signInWithPassword = vi.fn().mockResolvedValue({ error: null });

    await signInWithEmailPassword(
      clientWithAuth({ signInWithPassword }),
      "player@example.com",
      "correct horse battery staple",
    );

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: "player@example.com",
      password: "correct horse battery staple",
    });
  });

  it("reports when a new account requires email confirmation", async () => {
    const signUp = vi.fn().mockResolvedValue({ data: { session: null }, error: null });

    const outcome = await signUpWithEmailPassword(
      clientWithAuth({ signUp }),
      "player@example.com",
      "correct horse battery staple",
      "http://localhost:3000/auth/callback",
    );

    expect(outcome).toBe("confirmation_required");
    expect(signUp).toHaveBeenCalledWith({
      email: "player@example.com",
      password: "correct horse battery staple",
      options: { emailRedirectTo: "http://localhost:3000/auth/callback" },
    });
  });

  it("does not hide authentication errors", async () => {
    const failure = new Error("invalid credentials");
    const signInWithPassword = vi.fn().mockResolvedValue({ error: failure });

    await expect(
      signInWithEmailPassword(
        clientWithAuth({ signInWithPassword }),
        "player@example.com",
        "wrong password",
      ),
    ).rejects.toBe(failure);
  });
});
