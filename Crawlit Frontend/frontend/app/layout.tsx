import type { Metadata } from "next";
import "./globals.css";

import {Toaster} from "sonner"
export const metadata: Metadata = {
  title: "CrawlIt",
  description: "CrawlIt is a web application that allows users to clone GitHub repositories and interact with them. It provides a user-friendly interface for cloning repositories and managing their contents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster />
      </body>
    </html>
    
  );
}
