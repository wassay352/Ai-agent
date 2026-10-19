import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cloak Agent",
  description: "AI Agent Chat Interface",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gray-950 text-white">{children}</body>
    </html>
  );
}
