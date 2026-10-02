import type { Metadata } from "next";

import { SiteHeader } from "@/components/site-header";
import { ProfileDashboard } from "@/features/profile/profile-dashboard";

export const metadata: Metadata = { title: "Profile · DR. PROMPT" };

export default function ProfilePage() {
  return <div className="account-shell"><SiteHeader active="profile" /><ProfileDashboard /></div>;
}
