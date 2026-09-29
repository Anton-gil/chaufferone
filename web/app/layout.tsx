import type { Metadata } from "next";
import type { ReactNode } from "react";
import { VT323 } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";

const pixel = VT323({
  weight: ["400"],
  subsets: ["latin"],
  variable: "--font-pixel",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Chaufferone — The Obligation Engine",
  description: "Turn chaotic SMS alerts, emails, and chats into one intelligent, sequenced plan.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={pixel.variable}>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
