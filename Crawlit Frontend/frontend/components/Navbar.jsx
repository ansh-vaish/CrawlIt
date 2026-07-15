"use client";
import Link from "next/link";
import { GitHub } from "@deemlol/next-icons";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-stone-200/70 bg-[#F6F0E8] backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-stone-900 text-lg font-bold text-white shadow-sm">
            C
          </div>

          <div>
            <h1 className="text-lg font-bold tracking-tight text-stone-900">
              CrawlIt
            </h1>
            <p className="-mt-1 text-xs text-stone-500">
              AI Repository Intelligence
            </p>
          </div>
        </Link>

        {/* Desktop Actions */}
        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="https://github.com/ansh-vaish/CrawlIt"
            target="_blank"
            className="rounded-xl border border-stone-300 p-2 text-stone-700 transition hover:bg-stone-100"
          >
            <GitHub size={18} />
          </Link>
        </div>
      </nav>
    </header>
  );
}
