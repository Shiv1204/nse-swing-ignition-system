import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NSIS | Swing Trading Workstation",
  description: "Research and decision-support dashboard for NSE swing trading.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
