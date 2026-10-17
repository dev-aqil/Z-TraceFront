import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tracefront",
  description: "Real-time AI decision support for food safety incidents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">{children}</body>
    </html>
  );
}
