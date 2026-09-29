import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Sidebar, Topbar, FooterBar } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chaufferone · The one who holds every thread",
  description: "The one who holds every thread of your life admin.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="dashboard-layout">
          <Sidebar />
          <div className="main-content">
            <Topbar />
            <div style={{ flex: 1, overflow: "auto" }}>
              <div className="page-content">{children}</div>
            </div>
            <FooterBar />
          </div>
        </div>
      </body>
    </html>
  );
}
