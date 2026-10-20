import { useId } from "react";

// Logo (dark version): used on the dark top bar and the sign-in page.
export default function Logo({ height = 40 }: { height?: number }) {
  const id = useId().replace(/:/g, "");
  const w = (960 / 252) * height;
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="14 14 960 252" width={w} height={height} role="img" aria-label="Autonomous QA Execution Agent">
      <defs>
        <linearGradient id={`bg${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4F46E5" /><stop offset="1" stopColor="#0EA5E9" /></linearGradient>
        <linearGradient id={`ok${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#6EE7B7" /><stop offset="1" stopColor="#34D399" /></linearGradient>
      </defs>
      <g transform="translate(12,12)">
        <rect x="8" y="8" width="240" height="240" rx="56" fill={`url(#bg${id})`} />
        <g fill="none" stroke="#E0F7FF" strokeWidth="14" strokeLinecap="round"><path d="M62 120 A66 66 0 0 1 176 74" /><path d="M194 136 A66 66 0 0 1 80 182" /></g>
        <path d="M164 48 L196 70 L160 92 Z" fill="#fff" />
        <path d="M92 208 L60 186 L96 164 Z" fill="#fff" />
        <circle cx="128" cy="128" r="38" fill="#0B1220" opacity=".35" />
        <circle cx="128" cy="128" r="34" fill={`url(#ok${id})`} />
        <path d="M111 129 L123 141 L146 116" fill="none" stroke="#06281E" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <text x="290" y="140" fontFamily="Inter,Segoe UI,Helvetica,Arial,sans-serif" fontSize="80" fontWeight="800" fill="#FFFFFF" letterSpacing="-1">Autonomous QA</text>
      <text x="292" y="206" fontFamily="Inter,Segoe UI,Helvetica,Arial,sans-serif" fontSize="46" fontWeight="500" fill="#94A3B8" letterSpacing="7">EXECUTION AGENT</text>
    </svg>
  );
}
