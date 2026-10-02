import type { Metadata } from "next";

import { SiteHeader } from "@/components/site-header";
import { AccountDashboard } from "@/features/account/account-dashboard";

export const metadata: Metadata = { title: "Your progress · DR. PROMPT" };

export default function AccountPage() {
  return <div className="account-shell"><SiteHeader /><AccountDashboard /></div>;
}
