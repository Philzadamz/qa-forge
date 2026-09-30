import type { Metadata } from "next";

import { Providers } from "@/components/providers";
import { themeInitScript } from "@/components/theme-toggle";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "QA Forge", template: "%s · QA Forge" },
  description: "AI-assisted test case generation, reporting and test execution",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
