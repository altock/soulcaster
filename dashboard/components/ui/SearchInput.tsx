'use client';

export interface SearchInputProps {
  value: string;
  onChange: (nextValue: string) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
}

export default function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  className = '',
  inputClassName = '',
}: SearchInputProps) {
  return (
    <div className={`relative ${className}`}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
      >
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.3-4.3" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={`w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pl-10 pr-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 ${inputClassName}`}
      />
    </div>
  );
}

