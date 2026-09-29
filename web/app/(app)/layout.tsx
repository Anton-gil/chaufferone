import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { Sidebar, Topbar } from "@/components/Nav";
import { authOptions } from "@/lib/auth";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await getServerSession(authOptions);
  if (!session) redirect("/login");
  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="main-content">
        <Topbar />
        <div style={{ flex: 1, overflow: "auto" }}>
          <div className="page-content">{children}</div>
        </div>
      </div>
    </div>
  );
}
