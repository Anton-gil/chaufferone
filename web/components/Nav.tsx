"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Dashboard", icon: "" },
  { href: "/money", label: "Money", icon: "" },
  { href: "/graph", label: "Graph", icon: "" },
  { href: "/settings", label: "Settings", icon: "" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        Chaufferone
      </div>
      <div className="sidebar-nav">
        {items.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className={`sidebar-link ${pathname === it.href ? "active" : ""}`}
          >
            <span style={{ width: 20, textAlign: 'center' }}>{it.icon}</span>
            {it.label}
          </Link>
        ))}
      </div>
      <div style={{ marginTop: 'auto', padding: '0 24px', display: 'flex', gap: '16px', color: 'var(--text-muted)' }}>
      </div>
    </div>
  );
}

export function Topbar() {
  return (
    <div className="topbar">
      <div className="topbar-left">
      </div>
      <div className="topbar-right">
      </div>
    </div>
  );
}


