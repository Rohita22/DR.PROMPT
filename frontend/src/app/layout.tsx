import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "DR. PROMPT · Learn prompting by doing",
  description: "A hands-on prompt-engineering game with visible tests, hidden evaluations, objective scores, stars, and progression.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
