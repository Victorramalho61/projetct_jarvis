type IconProps = {
  name: string;
  size?: number;
  strokeWidth?: number;
  className?: string;
};

export default function Icon({ name, size = 18, strokeWidth = 1.75, className = "" }: IconProps) {
  const common = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth, strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const, className, "aria-hidden": true as const,
  };
  switch (name) {
    case "logo":
      return <svg {...common}><path d="M12 3 3 8l9 5 9-5-9-5z"/><path d="M3 13l9 5 9-5"/><path d="M3 18l9 5 9-5"/></svg>;
    case "mail":
      return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>;
    case "lock":
      return <svg {...common}><rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>;
    case "eye":
      return <svg {...common}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>;
    case "eye-off":
      return <svg {...common}><path d="M3 3l18 18"/><path d="M10.6 10.6A3 3 0 0 0 12 15a3 3 0 0 0 2.4-1.2"/><path d="M9.9 5.1A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a17.5 17.5 0 0 1-3.1 4.2"/><path d="M6.1 6.1C3.6 7.9 2 12 2 12s3.5 7 10 7a10.6 10.6 0 0 0 4.4-1"/></svg>;
    case "arrow-right":
      return <svg {...common}><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>;
    case "log-out":
      return <svg {...common}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>;
    case "menu":
      return <svg {...common}><path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h18"/></svg>;
    case "x":
      return <svg {...common}><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>;
    case "bell":
      return <svg {...common}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>;
    case "search":
      return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>;
    case "home":
      return <svg {...common}><path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z"/></svg>;
    case "sparkle":
      return <svg {...common}><path d="M12 3v3"/><path d="M12 18v3"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="m5.6 5.6 2.1 2.1"/><path d="m16.3 16.3 2.1 2.1"/><path d="m5.6 18.4 2.1-2.1"/><path d="m16.3 7.7 2.1-2.1"/></svg>;
    case "settings":
      return <svg {...common}><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m4.93 19.07 1.41-1.41"/><path d="m17.66 6.34 1.41-1.41"/><circle cx="12" cy="12" r="3"/></svg>;
    case "users":
      return <svg {...common}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>;
    case "file":
      return <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>;
    case "chart":
      return <svg {...common}><path d="M3 3v18h18"/><path d="m7 14 4-4 4 4 5-5"/></svg>;
    case "shield":
      return <svg {...common}><path d="M12 2 4 5v6c0 5 3.5 9.3 8 11 4.5-1.7 8-6 8-11V5z"/></svg>;
    case "check":
      return <svg {...common}><path d="M20 6 9 17l-5-5"/></svg>;
    case "chevron-right":
      return <svg {...common}><path d="m9 6 6 6-6 6"/></svg>;
    case "globe":
      return <svg {...common}><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 0 20"/><path d="M12 2a15 15 0 0 0 0 20"/></svg>;
    case "briefcase":
      return <svg {...common}><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>;
    case "cpu":
      return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M9 2v2"/><path d="M9 20v2"/><path d="M2 15h2"/><path d="M20 15h2"/><path d="M2 9h2"/><path d="M20 9h2"/></svg>;
    case "wallet":
      return <svg {...common}><path d="M20 12V8a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4"/><path d="M2 10h18"/><circle cx="17" cy="15" r="2"/></svg>;
    case "zap":
      return <svg {...common}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
    default:
      return <svg {...common}><circle cx="12" cy="12" r="9"/></svg>;
  }
}
