import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="border-t border-white/10 mt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          {/* Left side - Copyright */}
          <div className="text-slate-400 text-sm">
            © {new Date().getFullYear()} Soulcaster. All rights reserved.
          </div>

          {/* Right side - Links */}
          <div className="flex gap-6 text-sm">
            <Link
              href="/privacy"
              className="text-slate-400 hover:text-white transition-colors"
            >
              Privacy Policy
            </Link>
            <a
              href="https://github.com/altock/soulcaster"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white transition-colors"
            >
              GitHub
            </a>
            <a
              href="https://github.com/altock/soulcaster/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white transition-colors"
            >
              Support
            </a>
          </div>
        </div>

        {/* Research Preview Badge */}
        <div className="mt-4 pt-4 border-t border-white/5 text-center">
          <span className="inline-flex items-center gap-2 text-xs text-slate-500">
            <span className="w-2 h-2 bg-amber-400 rounded-full animate-pulse"></span>
            Research Preview
          </span>
        </div>
      </div>
    </footer>
  );
}
