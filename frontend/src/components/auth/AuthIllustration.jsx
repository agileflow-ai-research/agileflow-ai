/**
 * Decorative SVG illustration for the auth left-panel.
 * Depicts a stylised agile dashboard with kanban cards,
 * sprint progress, and AI-assist indicators — all drawn
 * with semi-transparent whites so it sits cleanly on any
 * gradient background.
 */
function AuthIllustration({ className }) {
  return (
    <svg
      data-testid="auth-illustration"
      className={className}
      viewBox="0 0 480 420"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* ── Main dashboard frame ── */}
      <rect
        x="40" y="30" width="400" height="360" rx="20"
        fill="white" fillOpacity="0.06"
        stroke="white" strokeOpacity="0.12" strokeWidth="1.5"
      />

      {/* Top bar */}
      <rect x="40" y="30" width="400" height="52" rx="20" fill="white" fillOpacity="0.04" />
      <rect x="40" y="80" width="400" height="1" fill="white" fillOpacity="0.08" />

      {/* Window dots */}
      <circle cx="68" cy="56" r="5" fill="#ef4444" fillOpacity="0.7" />
      <circle cx="86" cy="56" r="5" fill="#f59e0b" fillOpacity="0.7" />
      <circle cx="104" cy="56" r="5" fill="#22c55e" fillOpacity="0.7" />

      {/* Title bar text placeholder */}
      <rect x="180" y="50" width="120" height="12" rx="6" fill="white" fillOpacity="0.15" />

      {/* ── Sidebar ── */}
      <rect x="40" y="80" width="90" height="310" fill="white" fillOpacity="0.03" />
      <rect x="130" y="80" width="1" height="310" fill="white" fillOpacity="0.06" />

      {/* Sidebar items */}
      <rect x="56" y="100" width="58" height="8" rx="4" fill="white" fillOpacity="0.2" />
      <rect x="56" y="120" width="48" height="8" rx="4" fill="white" fillOpacity="0.1" />
      <rect x="56" y="140" width="52" height="8" rx="4" fill="white" fillOpacity="0.1" />

      {/* Active sidebar item highlight */}
      <rect x="48" y="161" width="74" height="28" rx="8" fill="white" fillOpacity="0.1" />
      <rect x="56" y="170" width="42" height="8" rx="4" fill="white" fillOpacity="0.3" />
      {/* Active dot */}
      <circle cx="108" cy="175" r="3" fill="#a855f7" />

      <rect x="56" y="204" width="50" height="8" rx="4" fill="white" fillOpacity="0.08" />
      <rect x="56" y="224" width="38" height="8" rx="4" fill="white" fillOpacity="0.08" />

      {/* ── Column headers (To Do / In Progress / Done) ── */}
      <rect x="148" y="92" width="56" height="10" rx="5" fill="white" fillOpacity="0.18" />
      <rect x="262" y="92" width="72" height="10" rx="5" fill="white" fillOpacity="0.18" />
      <rect x="374" y="92" width="44" height="10" rx="5" fill="white" fillOpacity="0.18" />

      {/* Column dividers */}
      <rect x="247" y="86" width="1" height="304" fill="white" fillOpacity="0.05" />
      <rect x="360" y="86" width="1" height="304" fill="white" fillOpacity="0.05" />

      {/* ── To Do column cards ── */}
      {/* Card 1 */}
      <rect x="148" y="116" width="86" height="72" rx="10" fill="white" fillOpacity="0.07" stroke="white" strokeOpacity="0.1" />
      <rect x="158" y="128" width="50" height="7" rx="3.5" fill="white" fillOpacity="0.25" />
      <rect x="158" y="142" width="66" height="5" rx="2.5" fill="white" fillOpacity="0.1" />
      <rect x="158" y="152" width="44" height="5" rx="2.5" fill="white" fillOpacity="0.1" />
      {/* Priority dot */}
      <circle cx="222" cy="175" r="4" fill="#f59e0b" fillOpacity="0.7" />
      {/* Story points badge */}
      <rect x="158" y="168" width="22" height="14" rx="7" fill="white" fillOpacity="0.1" />
      <text x="169" y="179" textAnchor="middle" fill="white" fillOpacity="0.4" fontSize="8" fontWeight="600">3</text>

      {/* Card 2 */}
      <rect x="148" y="200" width="86" height="60" rx="10" fill="white" fillOpacity="0.07" stroke="white" strokeOpacity="0.1" />
      <rect x="158" y="212" width="60" height="7" rx="3.5" fill="white" fillOpacity="0.25" />
      <rect x="158" y="226" width="56" height="5" rx="2.5" fill="white" fillOpacity="0.1" />
      <circle cx="222" cy="247" r="4" fill="#ef4444" fillOpacity="0.6" />
      <rect x="158" y="240" width="22" height="14" rx="7" fill="white" fillOpacity="0.1" />
      <text x="169" y="251" textAnchor="middle" fill="white" fillOpacity="0.4" fontSize="8" fontWeight="600">5</text>

      {/* Card 3 (small) */}
      <rect x="148" y="272" width="86" height="48" rx="10" fill="white" fillOpacity="0.05" stroke="white" strokeOpacity="0.08" />
      <rect x="158" y="284" width="46" height="7" rx="3.5" fill="white" fillOpacity="0.2" />
      <rect x="158" y="298" width="62" height="5" rx="2.5" fill="white" fillOpacity="0.08" />

      {/* ── In Progress column cards ── */}
      {/* Active card (highlighted) */}
      <rect x="260" y="116" width="88" height="80" rx="10" fill="white" fillOpacity="0.09" stroke="#a855f7" strokeOpacity="0.4" strokeWidth="1.5" />
      {/* AI sparkle icon */}
      <g transform="translate(328, 128)">
        <path d="M6 0L7.5 4.5L12 6L7.5 7.5L6 12L4.5 7.5L0 6L4.5 4.5Z" fill="#a855f7" fillOpacity="0.8">
          <animate attributeName="fillOpacity" values="0.5;0.9;0.5" dur="2.4s" repeatCount="indefinite" />
        </path>
      </g>
      <rect x="270" y="130" width="52" height="7" rx="3.5" fill="white" fillOpacity="0.3" />
      <rect x="270" y="144" width="68" height="5" rx="2.5" fill="white" fillOpacity="0.12" />
      <rect x="270" y="154" width="48" height="5" rx="2.5" fill="white" fillOpacity="0.12" />
      {/* Progress bar */}
      <rect x="270" y="170" width="68" height="6" rx="3" fill="white" fillOpacity="0.08" />
      <rect x="270" y="170" width="45" height="6" rx="3" fill="#a855f7" fillOpacity="0.5">
        <animate attributeName="width" values="30;45;42;45" dur="3s" repeatCount="indefinite" />
      </rect>
      {/* Assignee avatar */}
      <circle cx="274" cy="185" r="8" fill="white" fillOpacity="0.12" stroke="white" strokeOpacity="0.15" />
      <circle cx="274" cy="182" r="3" fill="white" fillOpacity="0.25" />
      <ellipse cx="274" cy="189" rx="5" ry="3" fill="white" fillOpacity="0.2" />

      {/* Card 2 */}
      <rect x="260" y="210" width="88" height="64" rx="10" fill="white" fillOpacity="0.07" stroke="white" strokeOpacity="0.1" />
      <rect x="270" y="222" width="58" height="7" rx="3.5" fill="white" fillOpacity="0.25" />
      <rect x="270" y="236" width="50" height="5" rx="2.5" fill="white" fillOpacity="0.1" />
      {/* Progress bar */}
      <rect x="270" y="252" width="68" height="6" rx="3" fill="white" fillOpacity="0.08" />
      <rect x="270" y="252" width="28" height="6" rx="3" fill="#38bdf8" fillOpacity="0.5" />
      <rect x="270" y="264" width="22" height="14" rx="7" fill="white" fillOpacity="0.1" />
      <text x="281" y="275" textAnchor="middle" fill="white" fillOpacity="0.4" fontSize="8" fontWeight="600">2</text>

      {/* ── Done column cards ── */}
      {/* Card 1 (completed) */}
      <rect x="374" y="116" width="54" height="60" rx="10" fill="white" fillOpacity="0.05" stroke="#22c55e" strokeOpacity="0.25" />
      <rect x="384" y="128" width="34" height="7" rx="3.5" fill="white" fillOpacity="0.18" />
      <rect x="384" y="142" width="28" height="5" rx="2.5" fill="white" fillOpacity="0.08" />
      {/* Check circle */}
      <circle cx="400" cy="162" r="7" fill="none" stroke="#22c55e" strokeOpacity="0.6" strokeWidth="1.5" />
      <path d="M395 162l3 3 5-6" stroke="#22c55e" strokeOpacity="0.6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />

      {/* Card 2 (completed) */}
      <rect x="374" y="188" width="54" height="52" rx="10" fill="white" fillOpacity="0.04" stroke="#22c55e" strokeOpacity="0.15" />
      <rect x="384" y="200" width="30" height="7" rx="3.5" fill="white" fillOpacity="0.15" />
      <rect x="384" y="214" width="34" height="5" rx="2.5" fill="white" fillOpacity="0.06" />
      <circle cx="400" cy="228" r="7" fill="none" stroke="#22c55e" strokeOpacity="0.4" strokeWidth="1.5" />
      <path d="M395 228l3 3 5-6" stroke="#22c55e" strokeOpacity="0.4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />

      {/* ── Sprint progress bar (bottom of dashboard) ── */}
      <rect x="148" y="348" width="280" height="30" rx="8" fill="white" fillOpacity="0.04" />
      <rect x="158" y="356" width="32" height="7" rx="3.5" fill="white" fillOpacity="0.14" />
      <rect x="200" y="358" width="140" height="10" rx="5" fill="white" fillOpacity="0.06" />
      <rect x="200" y="358" width="84" height="10" rx="5" fill="#a855f7" fillOpacity="0.3">
        <animate attributeName="width" values="70;84;80;84" dur="4s" repeatCount="indefinite" />
      </rect>
      <text x="410" y="366" textAnchor="end" fill="white" fillOpacity="0.35" fontSize="9" fontWeight="500">60%</text>

      {/* ── Floating AI assistant indicator ── */}
      <g>
        <rect x="362" y="300" width="72" height="32" rx="16" fill="white" fillOpacity="0.1" stroke="#a855f7" strokeOpacity="0.3" />
        {/* AI sparkle */}
        <g transform="translate(374, 310)">
          <path d="M4 0L5 3L8 4L5 5L4 8L3 5L0 4L3 3Z" fill="#a855f7" fillOpacity="0.7">
            <animate attributeName="fillOpacity" values="0.4;0.8;0.4" dur="1.8s" repeatCount="indefinite" />
          </path>
        </g>
        <text x="390" y="320" fill="white" fillOpacity="0.5" fontSize="9" fontWeight="600">AI Assist</text>
      </g>
    </svg>
  )
}

export default AuthIllustration
