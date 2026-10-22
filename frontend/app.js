/* =========================================================
   FinSync web app
   Plain JS, no build step. Hash routes:
     #/            Home
     #/new         New check
     #/checks      All checks
     #/checks/:id  One check (?tab=summary|records|review|followups|history)
     #/people      Customers & vendors
     #/people/:n   One person
     #/help        How it works
     #/account     Account
   ========================================================= */

const MAX_UPLOAD_MB = 15;
const ALLOWED_EXTS = [".csv", ".pdf", ".png", ".jpg", ".jpeg", ".txt"];

const state = {
  sb: null,            // Supabase client (null in local mode)
  authEnabled: false,
  session: null,
  user: null,          // { id, email, name }
  checks: null,        // cached list from /api/v1/checks
  draftFiles: [],      // files picked on the New check page
  draftText: "",
};

/* ---------------------------------------------------------
   Small helpers
   --------------------------------------------------------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* Line icons (Lucide, ISC licence), 24px grid, drawn with currentColor. */
const ICONS = {
  home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  checks: '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
  bank: '<path d="M3 22h18"/><path d="M6 18v-7"/><path d="M10 18v-7"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M12 2 20 7H4Z"/>',
  chat: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
  phone: '<rect width="14" height="20" x="5" y="2" rx="2"/><path d="M12 18h.01"/>',
  receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  checkCircle: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  half: '<circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 0 20Z" fill="currentColor" stroke="none"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  alertCircle: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  dashed: '<path d="M10.1 2.18a9.93 9.93 0 0 1 3.8 0"/><path d="M17.6 3.71a9.95 9.95 0 0 1 2.69 2.7"/><path d="M21.82 10.1a9.93 9.93 0 0 1 0 3.8"/><path d="M20.29 17.6a9.95 9.95 0 0 1-2.7 2.69"/><path d="M13.9 21.82a9.94 9.94 0 0 1-3.8 0"/><path d="M6.4 20.29a9.95 9.95 0 0 1-2.69-2.7"/><path d="M2.18 13.9a9.93 9.93 0 0 1 0-3.8"/><path d="M3.71 6.4a9.95 9.95 0 0 1 2.7-2.69"/>',
  fork: '<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  unlink: '<path d="m18.84 12.25 1.72-1.71h-.02a5 5 0 0 0-.12-7.07 5 5 0 0 0-6.95 0l-1.72 1.71"/><path d="m5.17 11.75-1.71 1.71a5 5 0 0 0 .12 7.07 5 5 0 0 0 6.95 0l1.71-1.71"/><path d="M8 2v3"/><path d="M2 8h3"/><path d="M16 19v3"/><path d="M19 16h3"/>',
  send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  cash: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
  undo: '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
  tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
  bag: '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>',
  rupee: '<path d="M6 3h12"/><path d="M6 8h12"/><path d="m6 13 8.5 8"/><path d="M6 13h3"/><path d="M9 13c6.667 0 6.667-10 0-10"/>',
  swap: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  userX: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m17 8 5 5"/><path d="m22 8-5 5"/>',
  calendarX: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><path d="m14 14-4 4"/><path d="m10 14 4 4"/>',
  searchX: '<path d="m13.5 8.5-5 5"/><path d="m8.5 8.5 5 5"/><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  cloudOff: '<path d="m2 2 20 20"/><path d="M5.782 5.782A7 7 0 0 0 9 19h8.5a4.5 4.5 0 0 0 1.307-.193"/><path d="M21.532 16.5A4.5 4.5 0 0 0 17.5 10h-1.79A7.008 7.008 0 0 0 10 5.07"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
  hourglass: '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
  compass: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z"/>',
  arrowLeft: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  arrowUp: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  arrowIn: '<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
  arrowOut: '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  folder: '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
  pen: '<path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/>',
  mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
  fileSearch: '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M4.268 21a2 2 0 0 0 1.727 1H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3"/><path d="m9 18-1.5-1.5"/><circle cx="5" cy="14" r="3"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
  plusCircle: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
  minusCircle: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
  thumbUp: '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>',
  thumbDown: '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  play: '<circle cx="12" cy="12" r="10"/><path d="m10 8 6 4-6 4Z"/>',
  eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
  dot: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  circle: '<circle cx="12" cy="12" r="10"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  monitor: '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
};

// Older call sites use descriptive names; map them onto the icon set.
const ICON_ALIAS = {
  add: "plus", upload_file: "upload", account_balance: "bank", receipt_long: "receipt", smartphone: "phone",
  close: "x", bolt: "check", check_circle: "checkCircle", timelapse: "half", error: "alertCircle", help: "dashed",
  contrast: "fork", content_copy: "copy", link_off: "unlink", radio_button_unchecked: "circle", send_money: "send",
  call_received: "inbox", payments: "cash", sell: "tag", shopping_bag: "bag", currency_rupee: "rupee",
  swap_horiz: "swap", person_alert: "userX", event_busy: "calendarX", search_off: "searchX", report: "alert",
  description: "file", cloud_off: "cloudOff", fact_check: "checks", group: "users", lightbulb: "help",
  hourglass_top: "hourglass", tour: "compass", arrow_back: "arrowLeft", summarize: "file", folder_open: "folder",
  rate_review: "pen", outgoing_mail: "mail", verified: "shield", auto_awesome: "sparkles", arrow_upward: "arrowUp",
  add_circle: "plusCircle", remove_circle: "minusCircle", south_west: "arrowIn", north_east: "arrowOut",
  thumb_up: "thumbUp", thumb_down: "thumbDown", notifications_active: "bell", gavel: "scale",
  find_in_page: "fileSearch", menu_book: "book", draft: "file", delete: "trash", verified_user: "shield",
  play_circle: "play", sticky_note_2: "file", visibility: "eye", add_task: "plusCircle", task_alt: "checkCircle",
  priority_high: "alert", radio_button_checked: "dot", chevron_right: "chevronRight", person: "user",
  more_horiz: "more", waving_hand: "compass", rocket_launch: "plus", chat: "chat", info: "info", lock: "lock",
  home: "home", search: "search", history: "history", flag: "flag", check: "check", refresh: "refresh",
  download: "download", logout: "logout", tag: "tag", undo: "undo",
};

function icon(name, cls = "") {
  const key = ICONS[name] ? name : ICON_ALIAS[name] || "circle";
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[key]}</svg>`;
}

const inrFmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inrFmt2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
function inr(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  return Number.isInteger(v) ? inrFmt.format(v) : inrFmt2.format(v);
}

function parseDate(v) {
  if (!v) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}
function fmtDate(v, withTime = false) {
  const d = parseDate(v);
  if (!d) return v ? String(v) : "—";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}) });
}
function relTime(v) {
  const d = parseDate(v);
  if (!d) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "Just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return fmtDate(v);
}

function fmtSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || "?") + (parts[1]?.[0] || "")).toUpperCase();
}

function titleCase(s) {
  return String(s || "").toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/* ---------------------------------------------------------
   Plain-language dictionaries
   --------------------------------------------------------- */
const STATUS = {
  CONFIRMED:         { label: "Matched",       tone: "green", icon: "check_circle", help: "The payment was found in your bank statement for the right amount." },
  PARTIAL:           { label: "Part paid",     tone: "amber", icon: "timelapse",    help: "Some money arrived, but less than what was billed or promised." },
  PARTIALLY_SETTLED: { label: "Part paid",     tone: "amber", icon: "timelapse",    help: "Some money arrived, but less than what was billed or promised." },
  CONTRADICTED:      { label: "Mismatch",      tone: "red",   icon: "error",        help: "Your records disagree with the bank — e.g. a different amount, reference or direction." },
  UNVERIFIABLE:      { label: "No bank proof", tone: "gray",  icon: "help",         help: "Someone says they paid, but no matching bank entry was found. Add the bank statement for that period." },
  AMBIGUOUS:         { label: "Unclear",       tone: "amber", icon: "contrast",     help: "More than one bank entry could match. You decide which one is right." },
  DUPLICATE:         { label: "Duplicate",     tone: "blue",  icon: "content_copy", help: "The same payment shows up more than once (e.g. a screenshot and a bank line). It's only counted once." },
  UNMATCHED:         { label: "Unmatched",     tone: "gray",  icon: "link_off",     help: "A bank entry or bill with nothing to pair it with yet." },
};
function statusMeta(s) {
  return STATUS[s] || { label: titleCase(s || "Unknown"), tone: "gray", icon: "radio_button_unchecked", help: "" };
}
function statusPill(s, lg = false) {
  const m = statusMeta(s);
  return `<span class="pill tone-${m.tone}${lg ? " lg" : ""}">${icon(m.icon, "fill")}${esc(m.label)}</span>`;
}

const REVIEW_LABEL = {
  NOT_REQUIRED: "No review needed", PENDING: "Waiting for you", IN_PROGRESS: "In review",
  ESCALATED: "Escalated", RESOLVED: "Reviewed", CLOSED: "Closed",
};
const DECISION_LABEL = {
  CONFIRMED: "Confirmed by you", REJECTED: "Marked as wrong", NEEDS_MORE_EVIDENCE: "Waiting for more proof",
  ESCALATED: "Escalated", ACKNOWLEDGED: "Settled outside the bank", UNRESOLVED: "Unresolved",
};

const CLAIM_TYPE = {
  PAYMENT_SENT: { label: "Says they paid", icon: "send_money" },
  PAYMENT_RECEIVED: { label: "Says payment received", icon: "call_received" },
  INVOICE_ISSUED: { label: "Invoice / bill", icon: "receipt_long" },
  CASH_PAYMENT_PROMISE: { label: "Cash / promise", icon: "payments" },
  REFUND_REQUESTED: { label: "Refund asked", icon: "undo" },
  DISCOUNT_APPLIED: { label: "Discount", icon: "sell" },
  EXPENSE_INCURRED: { label: "Expense", icon: "shopping_bag" },
};

const ISSUE = {
  AMOUNT_MISMATCH: { label: "Amounts don't match", icon: "currency_rupee" },
  REFERENCE_MISMATCH: { label: "Reference number doesn't match", icon: "tag" },
  DIRECTION_MISMATCH: { label: "Money moved the wrong way", icon: "swap_horiz" },
  ENTITY_MISMATCH: { label: "Different person or company", icon: "person_alert" },
  COUNTERPARTY_MISMATCH: { label: "Different person or company", icon: "person_alert" },
  DATE_MISMATCH: { label: "Dates don't line up", icon: "event_busy" },
  DUPLICATE_PAYMENT: { label: "Paid twice", icon: "content_copy" },
  MISSING_LEDGER_PROOF: { label: "No bank entry found", icon: "search_off" },
};
function issueMeta(t) { return ISSUE[t] || { label: titleCase(t), icon: "report" }; }

const SEVERITY = {
  CRITICAL: { label: "Serious", tone: "red" },
  ERROR: { label: "Important", tone: "amber" },
  WARNING: { label: "Check this", tone: "amber" },
  INFO: { label: "Note", tone: "gray" },
};
function severityPill(s) {
  const m = SEVERITY[s] || { label: titleCase(s), tone: "gray" };
  return `<span class="pill tone-${m.tone}">${esc(m.label)}</span>`;
}

const MODALITY = {
  BANK_STATEMENT: { label: "Bank statement", icon: "account_balance", tone: "brand" },
  INVOICE: { label: "Invoice", icon: "receipt_long", tone: "blue" },
  MESSAGING_CHAT: { label: "Chat message", icon: "chat", tone: "green" },
  PAYMENT_SCREENSHOT: { label: "Payment screenshot", icon: "smartphone", tone: "amber" },
  CASH_VOUCHER: { label: "Cash receipt", icon: "payments", tone: "gray" },
};
function modalityMeta(m) { return MODALITY[m] || { label: titleCase(m), icon: "description", tone: "gray" }; }

function fileKind(name) {
  const ext = (name.match(/\.[^.]+$/)?.[0] || "").toLowerCase();
  if (ext === ".csv") return { label: "Bank statement (CSV)", icon: "account_balance", tone: "brand", bank: true };
  if (ext === ".pdf") return { label: "Invoice or document (PDF)", icon: "receipt_long", tone: "blue" };
  if ([".png", ".jpg", ".jpeg"].includes(ext)) return { label: "Payment screenshot", icon: "smartphone", tone: "amber" };
  if (ext === ".txt") return { label: "Chat export / text", icon: "chat", tone: "green" };
  return { label: "File", icon: "description", tone: "gray" };
}

/* ---------------------------------------------------------
   Toasts & modal
   --------------------------------------------------------- */
function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(type === "error" ? "error" : type === "success" ? "check_circle" : "info", "fill")}<div>${esc(msg)}</div>`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), type === "error" ? 6000 : 3500);
}

function confirmDialog({ title, body, confirm = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const wrap = document.createElement("div");
    wrap.className = "modal-backdrop";
    wrap.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
        <h3 id="dlg-title">${esc(title)}</h3>
        <p>${esc(body)}</p>
        <div class="actions">
          <button class="btn btn-secondary" data-act="no">Cancel</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="yes">${esc(confirm)}</button>
        </div>
      </div>`;
    const close = (v) => { wrap.remove(); resolve(v); };
    wrap.addEventListener("click", (e) => {
      if (e.target === wrap) close(false);
      const act = e.target.closest("[data-act]")?.dataset.act;
      if (act) close(act === "yes");
    });
    document.body.appendChild(wrap);
    $("[data-act=yes]", wrap).focus();
  });
}

/* ---------------------------------------------------------
   API
   --------------------------------------------------------- */
class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (state.session?.access_token) headers.Authorization = `Bearer ${state.session.access_token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }

  let res;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError("Can't reach FinSync. Check your internet connection and try again.", 0);
  }
  if (res.status === 401 && state.authEnabled) {
    await signOut(true);
    throw new ApiError("Your session ended. Please sign in again.", 401);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.error?.message || data?.detail || `Something went wrong (${res.status}).`;
    throw new ApiError(msg, res.status);
  }
  return data;
}

async function loadChecks(force = false) {
  if (!force && state.checks) return state.checks;
  state.checks = await api("/api/v1/checks");
  updateBadges();
  return state.checks;
}
function invalidateChecks() { state.checks = null; }

function needsAttention(c) {
  return c.requires_review && !["RESOLVED", "CLOSED"].includes(c.review_status || "");
}

/* ---------------------------------------------------------
   Auth (Supabase)
   The app only renders behind a valid Supabase session. If the
   server says auth is required and anything is missing (config,
   Supabase library, session) the user stays on a locked screen.
   --------------------------------------------------------- */
const LIMITS = { nameMin: 2, nameMax: 50, emailMax: 254, pwMin: 8, pwMax: 72 };
const RESEND_COOLDOWN_S = 60;

async function initAuth() {
  let cfg;
  try {
    const res = await fetch("/api/v1/config", { cache: "no-store" });
    if (!res.ok) throw new Error();
    cfg = await res.json();
  } catch {
    state.bootError = "Can't reach FinSync right now. Check your connection and try again.";
    return;
  }

  if (!cfg.auth_required) {
    // Local development without Supabase: single local workspace.
    state.user = { id: "local", email: null, name: "You" };
    return;
  }

  state.authEnabled = true;
  if (!cfg.supabase_url || !cfg.supabase_anon_key || !window.supabase) {
    state.bootError = "Sign-in is temporarily unavailable. Please try again in a few minutes.";
    return;
  }

  const redirect = readAuthRedirect(); // must run before Supabase consumes the URL
  state.sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key, {
    // Implicit flow: links from emails work on any device, not only the browser that asked for them.
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "implicit" },
  });

  // getUser() checks the token with Supabase instead of trusting local storage.
  const { data: sessionData } = await state.sb.auth.getSession();
  if (sessionData.session) {
    const { data: userData, error } = await state.sb.auth.getUser();
    setSession(error || !userData.user ? null : sessionData.session);
    if (error) await state.sb.auth.signOut({ scope: "local" }).catch(() => {});
  }

  handleAuthRedirect(redirect);

  state.sb.auth.onAuthStateChange((event, session) => {
    const wasSignedIn = !!state.user;
    setSession(session);
    if (event === "PASSWORD_RECOVERY") {
      state.recovery = true;
      render();
      return;
    }
    if (event === "SIGNED_OUT") { state.recovery = false; caseCache.clear(); }
    if (!!state.user !== wasSignedIn) { invalidateChecks(); render(); }
  });
}

/* What a confirmation / reset email link put in the URL, if anything. */
function readAuthRedirect() {
  const query = new URLSearchParams(location.search);
  const rawHash = location.hash.replace(/^#/, "");
  const hash = rawHash.startsWith("/") ? new URLSearchParams() : new URLSearchParams(rawHash);
  return {
    err: query.get("error_description") || hash.get("error_description"),
    errCode: query.get("error_code") || hash.get("error_code") || "",
    type: hash.get("type") || query.get("type") || "",
    fromEmail: hash.has("access_token") || query.has("code") || hash.has("error") || query.has("error"),
  };
}

/* Turns the link result into a message (or the set-new-password screen) and cleans the URL. */
function handleAuthRedirect({ err, errCode, type, fromEmail }) {
  if (!fromEmail && !err) return;

  if (err) {
    const expired = /expired|invalid/i.test(errCode + " " + err);
    state.authNotice = {
      ok: false,
      text: expired
        ? "That link has expired or was already used. If you already confirmed your email, just sign in. Otherwise sign up again or use \"Forgot your password?\" to get a new link."
        : `The link didn't work: ${err}`,
    };
  } else if (state.user && type === "recovery") {
    state.recovery = true;
  } else if (state.user) {
    state.authNotice = null;
    state.welcomeToast = type === "signup" ? "Email confirmed. Welcome to FinSync!" : null;
  } else {
    state.authNotice = { ok: true, text: "Your email is confirmed. Sign in below to continue." };
  }
  history.replaceState(null, "", location.pathname + "#/");
}

function setSession(session) {
  state.session = session || null;
  const u = session?.user;
  state.user = u ? {
    id: u.id,
    email: u.email,
    name: u.user_metadata?.full_name || (u.email ? u.email.split("@")[0] : "You"),
  } : null;
}

async function signOut(silent = false) {
  if (state.sb) await state.sb.auth.signOut().catch(() => {});
  setSession(null);
  state.recovery = false;
  invalidateChecks();
  caseCache.clear();
  if (!silent) toast("You've been signed out.");
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  render();
}

function renderBootError() {
  $("#app").innerHTML = `
    <div class="auth-panel" style="min-height:100vh">
      <div class="auth-card" style="text-align:center;justify-items:center">
        <img src="assets/logo.svg" alt="" width="40" height="40">
        <h2>FinSync is unavailable</h2>
        <p class="muted">${esc(state.bootError)}</p>
        <button class="btn btn-primary" onclick="location.reload()">${icon("refresh")}Try again</button>
      </div>
    </div>`;
}

/* --- Validation --- */
const EMAIL_RE = /^[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}$/;
const NAME_RE = /^[\p{L}][\p{L}\p{M} .'-]*$/u;
const DOMAIN_TYPOS = {
  "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmal.com": "gmail.com", "gnail.com": "gmail.com",
  "gamil.com": "gmail.com", "gmail.co": "gmail.com", "gmail.cm": "gmail.com", "gmail.con": "gmail.com", "gmaill.com": "gmail.com",
  "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "yahoo.co": "yahoo.com", "yhoo.com": "yahoo.com", "yahoo.con": "yahoo.com",
  "hotmial.com": "hotmail.com", "hotmal.com": "hotmail.com", "hotmail.co": "hotmail.com",
  "outlok.com": "outlook.com", "outllook.com": "outlook.com", "outlook.co": "outlook.com", "outlook.con": "outlook.com",
  "rediffmail.co": "rediffmail.com", "icloud.co": "icloud.com",
};

function validateName(v) {
  const name = v.trim().replace(/\s+/g, " ");
  if (!name) return "Enter your name.";
  if (name.length < LIMITS.nameMin) return `Name must be at least ${LIMITS.nameMin} letters.`;
  if (name.length > LIMITS.nameMax) return `Name can be at most ${LIMITS.nameMax} characters.`;
  if (!NAME_RE.test(name)) return "Use letters only (spaces, dots, apostrophes and hyphens are fine).";
  return "";
}

function validateEmail(v) {
  const email = v.trim();
  if (!email) return "Enter your email address.";
  if (email.length > LIMITS.emailMax) return `Email can be at most ${LIMITS.emailMax} characters.`;
  if (!email.includes("@")) return "Email needs an @, like name@gmail.com.";
  const domain = email.split("@")[1] || "";
  if (!domain.includes(".")) return `Finish the address, like name@${domain || "gmail"}.com.`;
  if (!EMAIL_RE.test(email) || email.includes("..")) return "That doesn't look like a complete email address, e.g. name@gmail.com.";
  const fix = DOMAIN_TYPOS[domain.toLowerCase()];
  if (fix) return `Did you mean ${email.split("@")[0]}@${fix}?`;
  return "";
}

const PW_RULES = [
  { id: "len", label: `${LIMITS.pwMin}–${LIMITS.pwMax} characters`, test: (p) => p.length >= LIMITS.pwMin && p.length <= LIMITS.pwMax },
  { id: "upper", label: "An uppercase letter", test: (p) => /[A-Z]/.test(p) },
  { id: "lower", label: "A lowercase letter", test: (p) => /[a-z]/.test(p) },
  { id: "digit", label: "A number", test: (p) => /\d/.test(p) },
  { id: "symbol", label: "A special character (!@#$…)", test: (p) => /[^A-Za-z0-9\s]/.test(p) },
];
function validatePassword(p) {
  const failed = PW_RULES.filter((r) => !r.test(p));
  return failed.length ? `Password needs: ${failed.map((r) => r.label.toLowerCase()).join(", ")}.` : "";
}
function pwChecklist(p) {
  return PW_RULES.map((r) => {
    const ok = r.test(p);
    return `<li class="${ok ? "ok" : ""}">${icon(ok ? "checkCircle" : "circle")}${esc(r.label)}</li>`;
  }).join("");
}

/* --- Sign-in attempt throttling (on top of Supabase's server-side limits) --- */
const ATTEMPT_KEY = "verity.auth.attempts";
function readAttempts() {
  try { return JSON.parse(localStorage.getItem(ATTEMPT_KEY)) || { fails: 0, until: 0 }; }
  catch { return { fails: 0, until: 0 }; }
}
function writeAttempts(a) { try { localStorage.setItem(ATTEMPT_KEY, JSON.stringify(a)); } catch { /* storage blocked */ } }
function lockSecondsLeft() { return Math.max(0, Math.ceil((readAttempts().until - Date.now()) / 1000)); }
function recordFailedSignIn() {
  const a = readAttempts();
  a.fails += 1;
  // 5 free tries, then 30s, 60s, 120s … capped at 15 minutes.
  if (a.fails >= 5) a.until = Date.now() + Math.min(900, 30 * 2 ** (a.fails - 5)) * 1000;
  writeAttempts(a);
}
function clearFailedSignIns() { writeAttempts({ fails: 0, until: 0 }); }

const cooldowns = {};
function startCooldown(key, seconds) { cooldowns[key] = Date.now() + seconds * 1000; }
function cooldownLeft(key) { return Math.max(0, Math.ceil(((cooldowns[key] || 0) - Date.now()) / 1000)); }

/* --- Screens --- */
function authShell(inner) {
  return `
    <div class="auth">
      <section class="auth-hero">
        <a class="brand" href="#/"><img src="assets/logo.svg" alt=""><b>FinSync</b></a>
        <div>
          <h1>Know who has really paid you.</h1>
          <p class="lead">Upload your bank statement with invoices, payment screenshots and WhatsApp messages. FinSync matches every claim to your bank in seconds.</p>
          <div class="auth-sample" aria-hidden="true">
            <div class="as-msg"><b>Vikram</b><span>maine 15000 google pay kar diye hain</span></div>
            <div class="as-line"><span>ICICI statement, UPI 419082390192</span><span>+₹12,000</span></div>
            <div class="as-result"><span class="pill tone-amber">${icon("half")}Part paid</span><span>₹3,000 still due</span></div>
          </div>
        </div>
        <p class="fine">For freelancers, agencies and small businesses in India.</p>
      </section>
      <section class="auth-panel">
        <div class="auth-card">
          <div class="auth-top">
            <a class="brand hide-desktop" href="#/"><img src="assets/logo.svg" alt=""><b>FinSync</b></a>
            ${themeToggleHtml()}
          </div>
          ${inner}
        </div>
      </section>
    </div>`;
}

function fieldHtml({ id, label, type = "text", max, auto, placeholder, hint = "" }) {
  return `
    <div class="field" id="${id}-field">
      <label for="${id}">${label}</label>
      <div class="input-wrap">
        <input class="input" id="${id}" type="${type}" maxlength="${max}" autocomplete="${auto}" placeholder="${esc(placeholder)}" spellcheck="false" autocapitalize="${type === "email" ? "none" : "words"}">
        ${type === "password" ? `<button type="button" class="reveal" data-reveal="${id}" aria-label="Show password">${icon("eye")}</button>` : ""}
      </div>
      <p class="field-error" id="${id}-error" role="alert" hidden></p>
      ${hint}
    </div>`;
}

function setFieldError(id, msg) {
  const el = $(`#${id}-error`);
  const input = $(`#${id}`);
  if (!el || !input) return;
  el.textContent = msg || "";
  el.hidden = !msg;
  input.setAttribute("aria-invalid", msg ? "true" : "false");
}

function wireReveal(root) {
  $$("[data-reveal]", root).forEach((b) => b.addEventListener("click", () => {
    const input = $(`#${b.dataset.reveal}`);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    b.setAttribute("aria-label", show ? "Hide password" : "Show password");
    b.classList.toggle("on", show);
  }));
}

function renderAuth(mode = "signin") {
  const app = $("#app");
  app.innerHTML = authShell(`
    <div>
      <h2 id="auth-title"></h2>
      <p class="sub" id="auth-sub"></p>
    </div>
    <div class="seg" role="tablist" id="auth-seg">
      <button role="tab" type="button" data-mode="signin">Sign in</button>
      <button role="tab" type="button" data-mode="signup">Create account</button>
    </div>
    <form id="auth-form" class="stack" novalidate>
      ${fieldHtml({ id: "auth-name", label: "Your name", max: LIMITS.nameMax, auto: "name", placeholder: "e.g. Priya Sharma" })}
      ${fieldHtml({ id: "auth-email", label: "Email", type: "email", max: LIMITS.emailMax, auto: "email", placeholder: "name@gmail.com" })}
      ${fieldHtml({ id: "auth-pw", label: "Password", type: "password", max: LIMITS.pwMax, auto: "current-password", placeholder: "Your password",
        hint: `<ul class="pw-rules" id="pw-rules" hidden></ul>` })}
      <div id="auth-msg" hidden></div>
      <button class="btn btn-primary btn-lg btn-block" id="auth-submit" type="submit"></button>
      <button class="link-btn" type="button" id="auth-forgot"></button>
    </form>`);

  let current = mode;
  let pendingEmail = "";
  const setMode = (m) => {
    current = m;
    $$("#auth-seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mode === m)));
    $("#auth-seg").hidden = m === "reset";
    $("#auth-title").textContent = { signin: "Welcome back", signup: "Create your account", reset: "Reset your password" }[m];
    $("#auth-sub").textContent = {
      signin: "Sign in to see your payment checks.",
      signup: "Your workspace starts empty and is private to you.",
      reset: "Enter your account email and we'll send you a link to set a new password.",
    }[m];
    $("#auth-name-field").hidden = m !== "signup";
    $("#auth-pw-field").hidden = m === "reset";
    $("#auth-pw").autocomplete = m === "signup" ? "new-password" : "current-password";
    $("#auth-pw").placeholder = m === "signup" ? "Create a strong password" : "Your password";
    $("#pw-rules").hidden = m !== "signup";
    $("#pw-rules").innerHTML = pwChecklist($("#auth-pw").value);
    $("#auth-forgot").textContent = m === "reset" ? "Back to sign in" : "Forgot your password?";
    $("#auth-msg").hidden = true;
    ["auth-name", "auth-email", "auth-pw"].forEach((id) => setFieldError(id, ""));
    updateSubmit();
  };

  const updateSubmit = () => {
    const btn = $("#auth-submit");
    const lock = current === "signin" ? lockSecondsLeft() : 0;
    const cool = current === "reset" ? cooldownLeft(`reset:${$("#auth-email").value.trim().toLowerCase()}`) : 0;
    btn.disabled = !!(lock || cool) || btn.dataset.busy === "1";
    btn.textContent = lock ? `Too many attempts. Try again in ${lock}s`
      : cool ? `Link sent. Resend in ${cool}s`
      : { signin: "Sign in", signup: "Create account", reset: "Send reset link" }[current];
  };
  const ticker = setInterval(() => {
    if (!document.body.contains($("#auth-submit"))) return clearInterval(ticker);
    updateSubmit();
    const resend = $("#resend-btn");
    if (resend) {
      const left = cooldownLeft(`signup:${pendingEmail}`);
      resend.disabled = left > 0;
      resend.textContent = left ? `Resend email in ${left}s` : "Resend confirmation email";
    }
  }, 1000);

  setMode(mode);
  if (state.authNotice) {
    showMsg(esc(state.authNotice.text), state.authNotice.ok);
    state.authNotice = null;
  }
  wireReveal(app);
  $$("#auth-seg button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  $("#auth-forgot").addEventListener("click", () => setMode(current === "reset" ? "signin" : "reset"));

  // Validate on blur, re-validate live once a field has shown an error.
  const validators = { "auth-name": validateName, "auth-email": validateEmail, "auth-pw": (v) => (current === "signup" ? validatePassword(v) : v ? "" : "Enter your password.") };
  Object.entries(validators).forEach(([id, fn]) => {
    const input = $(`#${id}`);
    input.addEventListener("blur", () => { if (input.value) setFieldError(id, fn(input.value)); });
    input.addEventListener("input", () => {
      if (input.getAttribute("aria-invalid") === "true") setFieldError(id, fn(input.value));
      if (id === "auth-pw") $("#pw-rules").innerHTML = pwChecklist(input.value);
      if (id === "auth-email") updateSubmit();
    });
  });

  function showMsg(html, ok = false) {
    const el = $("#auth-msg");
    el.className = ok ? "form-ok" : "form-error";
    el.innerHTML = html;
    el.hidden = false;
  }

  $("#auth-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("#auth-msg").hidden = true;
    const name = $("#auth-name").value.trim().replace(/\s+/g, " ");
    const email = $("#auth-email").value.trim().toLowerCase();
    const password = $("#auth-pw").value;

    const errors = {
      "auth-email": validateEmail(email),
      "auth-name": current === "signup" ? validateName(name) : "",
      "auth-pw": current === "reset" ? "" : validators["auth-pw"](password),
    };
    Object.entries(errors).forEach(([id, msg]) => setFieldError(id, msg));
    const firstBad = Object.keys(errors).find((k) => errors[k]);
    if (firstBad) { $(`#${firstBad}`).focus(); return; }
    if (current === "signin" && lockSecondsLeft()) return updateSubmit();

    const btn = $("#auth-submit");
    btn.dataset.busy = "1";
    updateSubmit();
    try {
      if (current === "signin") {
        const { error } = await state.sb.auth.signInWithPassword({ email, password });
        if (error) {
          if (!/email not confirmed/i.test(error.message)) recordFailedSignIn();
          throw error;
        }
        clearFailedSignIns();
      } else if (current === "signup") {
        const { data, error } = await state.sb.auth.signUp({
          email, password,
          options: { data: { full_name: name }, emailRedirectTo: location.origin },
        });
        if (error) throw error;
        if (!data.session) {
          pendingEmail = email;
          startCooldown(`signup:${email}`, RESEND_COOLDOWN_S);
          showMsg(`<b>Check your inbox.</b> We sent a confirmation link to ${esc(email)}. Open it, then sign in.<div class="mt-12"><button type="button" class="btn btn-secondary btn-sm" id="resend-btn" disabled>Resend email in ${RESEND_COOLDOWN_S}s</button></div>`, true);
          $("#resend-btn").addEventListener("click", async () => {
            startCooldown(`signup:${email}`, RESEND_COOLDOWN_S);
            const { error: rErr } = await state.sb.auth.resend({ type: "signup", email, options: { emailRedirectTo: location.origin } });
            toast(rErr ? friendlyAuthError(rErr) : "Confirmation email sent again.", rErr ? "error" : "success");
          });
        }
      } else {
        startCooldown(`reset:${email}`, RESEND_COOLDOWN_S);
        const { error } = await state.sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin });
        if (error && !/rate limit/i.test(error.message)) throw error;
        // Same message whether or not the account exists, so emails can't be probed.
        showMsg(`<b>Check your email.</b> If an account exists for ${esc(email)}, a password reset link is on its way. It expires in 1 hour.`, true);
      }
    } catch (err) {
      showMsg(esc(friendlyAuthError(err)));
    } finally {
      btn.dataset.busy = "";
      updateSubmit();
    }
  });
}

/* Shown after the user opens the reset link from their email. */
function renderNewPassword() {
  const app = $("#app");
  app.innerHTML = authShell(`
    <div>
      <h2>Set a new password</h2>
      <p class="sub">Choose a new password for ${esc(state.user?.email || "your account")}.</p>
    </div>
    <form id="np-form" class="stack" novalidate>
      ${fieldHtml({ id: "np-pw", label: "New password", type: "password", max: LIMITS.pwMax, auto: "new-password", placeholder: "Create a strong password", hint: `<ul class="pw-rules" id="np-rules">${pwChecklist("")}</ul>` })}
      ${fieldHtml({ id: "np-pw2", label: "Confirm new password", type: "password", max: LIMITS.pwMax, auto: "new-password", placeholder: "Type it again" })}
      <div id="np-msg" hidden></div>
      <button class="btn btn-primary btn-lg btn-block" id="np-submit" type="submit">Save new password</button>
    </form>`);
  wireReveal(app);
  $("#np-pw").addEventListener("input", (e) => { $("#np-rules").innerHTML = pwChecklist(e.target.value); });
  $("#np-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pw = $("#np-pw").value;
    const pw2 = $("#np-pw2").value;
    setFieldError("np-pw", validatePassword(pw));
    setFieldError("np-pw2", pw && pw !== pw2 ? "Passwords don't match." : "");
    if (validatePassword(pw) || pw !== pw2) return;
    const btn = $("#np-submit");
    btn.disabled = true;
    const { error } = await state.sb.auth.updateUser({ password: pw });
    btn.disabled = false;
    if (error) {
      const el = $("#np-msg");
      el.className = "form-error";
      el.textContent = friendlyAuthError(error);
      el.hidden = false;
      return;
    }
    state.recovery = false;
    clearFailedSignIns();
    toast("Password updated. You're signed in.", "success");
    history.replaceState(null, "", location.pathname + "#/");
    render();
  });
}

function friendlyAuthError(err) {
  const m = String(err?.message || err || "");
  if (/invalid login/i.test(m)) {
    const a = readAttempts();
    const left = Math.max(0, 5 - a.fails);
    return left ? `Email or password is incorrect. ${left} attempt${left === 1 ? "" : "s"} left before a short lockout.` : "Too many wrong attempts. Please wait before trying again, or reset your password.";
  }
  if (/email not confirmed/i.test(m)) return "Please confirm your email first. Check your inbox for the link.";
  if (/already registered|already been registered/i.test(m)) return "An account with this email already exists. Sign in instead.";
  if (/rate limit|too many|over_email_send_rate_limit/i.test(m)) return "Too many attempts. Please wait a minute and try again.";
  if (/weak|password should|password is known/i.test(m)) return "That password is too weak or too common. Try a longer one with a mix of characters.";
  if (/same.*password|should be different/i.test(m)) return "Your new password must be different from the old one.";
  if (/database error/i.test(m)) return "Please check your name and email and try again.";
  return m || "Something went wrong. Please try again.";
}

/* ---------------------------------------------------------
   Theme (light / dark / system)
   --------------------------------------------------------- */
const THEME_KEY = "verity.theme";
function getThemePref() { try { return localStorage.getItem(THEME_KEY) || "system"; } catch { return "system"; } }
function applyTheme(pref) {
  const root = document.documentElement;
  if (pref === "light" || pref === "dark") root.setAttribute("data-theme", pref);
  else root.removeAttribute("data-theme");
  const dark = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  $('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0E0E10" : "#FAFAFA");
  $$("[data-theme-set]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeSet === pref)));
}
function setThemePref(pref) {
  try { localStorage.setItem(THEME_KEY, pref); } catch { /* storage blocked */ }
  applyTheme(pref);
}
function themeToggleHtml() {
  const opts = [["light", "sun", "Light"], ["dark", "moon", "Dark"], ["system", "monitor", "System"]];
  const pref = getThemePref();
  return `<div class="theme-toggle" role="group" aria-label="Theme">${opts.map(([v, ic, label]) =>
    `<button type="button" data-theme-set="${v}" aria-pressed="${pref === v}" title="${label}" aria-label="${label} theme">${icon(ic)}</button>`).join("")}</div>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-theme-set]");
  if (b) setThemePref(b.dataset.themeSet);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => applyTheme(getThemePref()));

/* ---------------------------------------------------------
   Shell
   --------------------------------------------------------- */
const NAV = [
  { id: "home", href: "#/", label: "Home", icon: "home" },
  { id: "checks", href: "#/checks", label: "Checks", icon: "fact_check" },
  { id: "people", href: "#/people", label: "People", icon: "group" },
  { id: "help", href: "#/help", label: "How it works", icon: "lightbulb" },
];

function renderShell() {
  const u = state.user;
  const app = $("#app");
  app.innerHTML = `
    <div class="shell">
      <aside class="sidebar" aria-label="Main">
        <a class="brand" href="#/"><img src="assets/logo.svg" alt=""><b>FinSync</b></a>
        <a class="btn btn-primary btn-lg" href="#/new" data-tour="new">${icon("add")}New check</a>
        <nav class="stack" style="gap:4px">
          ${NAV.map((n) => `
            <a class="nav-link" href="${n.href}" data-nav="${n.id}" data-tour="${n.id}">
              ${icon(n.icon)}<span>${n.label}</span>${n.id === "checks" ? `<span class="badge" data-badge hidden></span>` : ""}
            </a>`).join("")}
        </nav>
        <div class="sidebar-foot">
          ${themeToggleHtml()}
          <a class="account-chip" href="#/account" data-nav="account" data-tour="account">
            <span class="avatar">${esc(initials(u.name))}</span>
            <span class="meta"><b>${esc(u.name)}</b><small>${esc(u.email || "Local workspace")}</small></span>
          </a>
        </div>
      </aside>

      <header class="topbar">
        <a class="brand" href="#/"><img src="assets/logo.svg" alt=""><b>FinSync</b></a>
        <a class="icon-btn" href="#/help" aria-label="How it works" data-tour="help">${icon("help")}</a>
      </header>

      <main class="main" id="view" tabindex="-1"></main>

      <nav class="bottom-nav" aria-label="Main">
        <a class="bn-item" href="#/" data-nav="home" data-tour="home">${icon("home")}Home</a>
        <a class="bn-item" href="#/checks" data-nav="checks" data-tour="checks">${icon("fact_check")}Checks<span class="badge" data-badge hidden></span></a>
        <a class="bn-new" href="#/new" aria-label="New check" data-tour="new"><span class="fab">${icon("add")}</span></a>
        <a class="bn-item" href="#/people" data-nav="people" data-tour="people">${icon("group")}People</a>
        <a class="bn-item" href="#/account" data-nav="account" data-tour="account">${icon("person")}Account</a>
      </nav>
    </div>`;
  updateBadges();
}

function setActiveNav(id) {
  $$("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === id));
}

function updateBadges() {
  const n = (state.checks || []).filter(needsAttention).length;
  $$("[data-badge]").forEach((b) => { b.hidden = !n; b.textContent = n; });
}

/* ---------------------------------------------------------
   Router
   --------------------------------------------------------- */
function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");
  return { parts: path.split("/").filter(Boolean).map(decodeURIComponent), query: new URLSearchParams(qs || "") };
}

let renderToken = 0;
async function render() {
  const token = ++renderToken;
  $("#boot").hidden = true;
  $("#app").hidden = false;

  if (state.bootError) { stopTour(); renderBootError(); return; }
  if (!state.user) {
    // Fail closed: without a verified session nothing but the sign-in screen renders.
    stopTour();
    if (!$(".auth") || $(".shell")) renderAuth();
    return;
  }
  if (state.recovery) { stopTour(); renderNewPassword(); return; }
  if (!$(".shell")) renderShell();

  const { parts, query } = parseHash();
  const view = $("#view");
  const [a, b] = parts;
  let nav = "home";
  try {
    if (!a) await viewHome(view);
    else if (a === "new") { nav = "new"; await viewNew(view); }
    else if (a === "checks" && b) { nav = "checks"; await viewCheck(view, b, query.get("tab") || "summary"); }
    else if (a === "checks") { nav = "checks"; await viewChecks(view, query); }
    else if (a === "people" && b) { nav = "people"; await viewPerson(view, b); }
    else if (a === "people") { nav = "people"; await viewPeople(view); }
    else if (a === "help") { nav = "help"; viewHelp(view); }
    else if (a === "account") { nav = "account"; viewAccount(view, query); }
    else { location.hash = "#/"; return; }
  } catch (err) {
    if (token !== renderToken) return;
    view.innerHTML = errorState(err);
  }
  if (token !== renderToken) return;
  setActiveNav(nav);
  maybeStartTours(a, b);
}

function errorState(err) {
  return `
    <div class="page">
      <div class="card empty">
        <div class="art" style="background:var(--red-soft);color:var(--red)">${icon("cloud_off")}</div>
        <h3>We couldn't load this page</h3>
        <p>${esc(err?.message || "Unknown error")}</p>
        <button class="btn btn-secondary" onclick="render()">${icon("refresh")}Try again</button>
      </div>
    </div>`;
}

function loadingState() {
  return `<div class="page stack">
    <div class="skeleton" style="height:36px;width:220px"></div>
    <div class="stats">${"<div class='skeleton' style='height:112px'></div>".repeat(4)}</div>
    <div class="skeleton" style="height:240px"></div>
  </div>`;
}

/* ---------------------------------------------------------
   Home
   --------------------------------------------------------- */
function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function checkRow(c) {
  const who = c.counterparty || (c.status === "UNMATCHED" ? "Unknown payer" : "Unnamed check");
  return `
    <li>
      <a class="row" href="#/checks/${encodeURIComponent(c.case_id)}">
        <span class="avatar">${esc(initials(who))}</span>
        <span class="main-col">
          <span class="title">${esc(who)}</span>
          <span class="meta"><span>${esc(relTime(c.created_at))}</span><span>${c.files_count} record${c.files_count === 1 ? "" : "s"}</span>${c.issues_count ? `<span class="t-red">${c.issues_count} issue${c.issues_count === 1 ? "" : "s"}</span>` : ""}</span>
        </span>
        <span class="end">
          <span class="amount">${inr(c.matched_amount)}</span>
          ${needsAttention(c) ? `<span class="pill tone-amber">${icon("flag")}Review</span>` : statusPill(c.status)}
        </span>
      </a>
    </li>`;
}

async function viewHome(view) {
  view.innerHTML = loadingState();
  const checks = await loadChecks(true);
  const u = state.user;

  const expected = checks.reduce((s, c) => s + (c.expected_amount || 0), 0);
  const received = checks.reduce((s, c) => s + (c.matched_amount || 0), 0);
  const due = checks.reduce((s, c) => s + (c.outstanding_amount || 0), 0);
  const attention = checks.filter(needsAttention);

  const stats = `
    <section class="stats stats-5" aria-label="Overview" data-tour="stats">
      <div class="stat"><span class="label">Expected</span><span class="value money">${inr(expected)}</span></div>
      <div class="stat"><span class="label">Confirmed in your bank</span><span class="value money t-green">${inr(received)}</span></div>
      <div class="stat"><span class="label">Still due</span><span class="value money ${due > 0 ? "t-amber" : ""}">${inr(due)}</span></div>
      <div class="stat"><span class="label">Checks run</span><span class="value">${checks.length}</span></div>
      <div class="stat"><span class="label">Waiting for your review</span><span class="value ${attention.length ? "t-red" : ""}">${attention.length}</span></div>
    </section>`;

  if (!checks.length) {
    view.innerHTML = `
      <div class="page">
        <div class="hello">
          <h1>${greeting()}, ${esc(u.name)}</h1>
          <p>Your workspace is empty and ready.</p>
        </div>
        <section class="panel start">
          <div class="start-copy">
            <h2>Run your first check</h2>
            <p>Add your bank statement and whatever proof you were sent: an invoice, a payment screenshot or a WhatsApp message. FinSync tells you what actually reached your bank.</p>
            <div class="row-actions mt-24">
              <a class="btn btn-primary btn-lg" href="#/new">${icon("plus")}New check</a>
              <button class="btn btn-secondary btn-lg" id="replay-tour">${icon("compass")}Show me around</button>
            </div>
          </div>
          <div class="venn-demo" aria-hidden="true">
            <div class="venn-row"><span class="vd-label">Ramesh on WhatsApp</span><span class="vd-amt">₹35,000</span></div>
            <div class="venn-row"><span class="vd-label">HDFC statement, 15 Aug</span><span class="vd-amt">₹35,000</span></div>
            <div class="venn-row result"><span class="pill tone-green">${icon("checkCircle")}Matched</span><span class="vd-amt">₹0 due</span></div>
          </div>
        </section>

        <ol class="steps">
          <li><span class="num">1</span><div><h3>Add your records</h3><p>A bank statement CSV, plus invoices, screenshots or chats.</p></div></li>
          <li><span class="num">2</span><div><h3>FinSync matches them</h3><p>Every claimed payment is compared with real entries in your statement.</p></div></li>
          <li><span class="num">3</span><div><h3>You get a clear answer</h3><p>Matched, part paid or mismatch, with the amount still due.</p></div></li>
        </ol>

        <h2 class="section-title">Overview</h2>
        ${stats}
        <p class="muted small mt-12">These fill in as you run checks.</p>
      </div>`;
    $("#replay-tour").addEventListener("click", () => startTour("main", true));
    return;
  }

  view.innerHTML = `
    <div class="page">
      <div class="hello">
        <h1>${greeting()}, ${esc(u.name)}</h1>
        <p>${attention.length ? `${attention.length} check${attention.length === 1 ? " needs" : "s need"} your attention.` : "Everything is up to date."}</p>
      </div>
      ${stats}

      <div class="dash mt-16">
        <section class="panel card-pad" aria-labelledby="recent-h">
          <div class="card-head"><h2 id="recent-h">Recent reconciliations</h2><a class="muted small" href="#/checks">View all</a></div>
          ${reconTable(checks.slice(0, 6))}
        </section>
        <section class="panel card-pad" aria-labelledby="status-h">
          <div class="card-head"><h2 id="status-h">Payment status</h2></div>
          ${statusDonut(checks)}
          ${collectionBar(received, expected)}
        </section>
      </div>

      ${attention.length ? `
        <h2 class="section-title">Waiting for your review <a href="#/checks?filter=review">View all</a></h2>
        <div class="panel"><ul class="list">${attention.slice(0, 4).map(checkRow).join("")}</ul></div>` : ""}
    </div>`;
}

/* --- Home dashboard pieces --- */
const TONE_COLOR = { green: "var(--green)", amber: "var(--amber)", red: "var(--red)", blue: "var(--blue)", gray: "var(--faint)" };

function reconTable(rows) {
  return `
    <div class="recon-wrap">
      <table class="recon">
        <thead><tr><th>Check</th><th class="num hide-sm">Expected</th><th class="num">Received</th><th>Status</th></tr></thead>
        <tbody>${rows.map((c) => {
          const who = c.counterparty || "Unnamed check";
          const due = (c.outstanding_amount || 0) > 0;
          return `<tr>
            <td><a href="#/checks/${encodeURIComponent(c.case_id)}">${esc(who)}</a><span class="muted small">${esc(relTime(c.created_at))}</span></td>
            <td class="num hide-sm">${inr(c.expected_amount)}</td>
            <td class="num ${due ? "t-amber" : ""}">${inr(c.matched_amount)}</td>
            <td>${statusPill(c.status)}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>
    </div>`;
}

function statusDonut(checks) {
  // Group by the label people see, so statuses that share a label share a slice.
  const groups = new Map();
  for (const c of checks) {
    const m = statusMeta(c.status);
    const g = groups.get(m.label) || { label: m.label, tone: m.tone, count: 0 };
    g.count += 1;
    groups.set(m.label, g);
  }
  const parts = [...groups.values()].sort((a, b) => b.count - a.count);
  const total = checks.length;
  const r = 52, len = 2 * Math.PI * r;
  let offset = 0;
  const arcs = parts.map((p) => {
    const share = (p.count / total) * len;
    const gap = parts.length > 1 ? Math.min(2, share / 3) : 0;
    const arc = `<circle cx="70" cy="70" r="${r}" fill="none" stroke="${TONE_COLOR[p.tone] || TONE_COLOR.gray}" stroke-width="20"
      stroke-dasharray="${(share - gap).toFixed(2)} ${(len - share + gap).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 70 70)"/>`;
    offset += share;
    return arc;
  }).join("");
  const summary = parts.map((p) => `${p.count} ${p.label}`).join(", ");
  return `
    <div class="donut-wrap">
      <svg class="donut" viewBox="0 0 140 140" role="img" aria-label="${esc(`Payment status: ${summary}`)}">
        <circle cx="70" cy="70" r="${r}" fill="none" stroke="var(--subtle)" stroke-width="20"/>
        ${arcs}
        <text x="70" y="68" text-anchor="middle" class="donut-num">${total}</text>
        <text x="70" y="86" text-anchor="middle" class="donut-cap">check${total === 1 ? "" : "s"}</text>
      </svg>
      <ul class="legend">${parts.map((p) => `
        <li><span class="sw" style="background:${TONE_COLOR[p.tone] || TONE_COLOR.gray}"></span><span>${esc(p.label)}</span><b>${p.count}</b></li>`).join("")}
      </ul>
    </div>`;
}

function collectionBar(received, expected) {
  if (!expected) return "";
  const pct = Math.max(0, Math.min(100, Math.round((received / expected) * 100)));
  return `
    <div class="collect mt-16">
      <div class="collect-top"><span class="muted small">Collected</span><span class="small"><b>${inr(received)}</b> of ${inr(expected)} · ${pct}%</span></div>
      <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="Collected ${pct}% of expected"><span style="width:${pct}%"></span></div>
    </div>`;
}

/* ---------------------------------------------------------
   New check
   --------------------------------------------------------- */
async function viewNew(view) {
  view.innerHTML = `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>New check</h1>
          <p>Add everything related to the payments you want to check.</p>
        </div>
      </div>

      <div class="new-layout">
        <section class="stack">
          <div class="dropzone" id="dz" tabindex="0" role="button" aria-label="Add files">
            <div class="art">${icon("upload_file")}</div>
            <h3>Drop files here or tap to choose</h3>
            <p>CSV, PDF, PNG, JPG or TXT, up to ${MAX_UPLOAD_MB} MB each</p>
            <input type="file" id="file-input" multiple accept="${ALLOWED_EXTS.join(",")}" hidden>
          </div>
          <div class="file-list" id="file-list"></div>

          <div class="card card-pad">
            <div class="field">
              <label for="paste">Or paste a message <span class="muted" style="font-weight:500">(optional)</span></label>
              <textarea class="textarea" id="paste" placeholder="e.g. Bhai 35,000 GPay kar diya, check kar lo"></textarea>
            </div>
            <p class="muted small mt-8">Works with WhatsApp or SMS text in English, Hinglish and Indian languages.</p>
          </div>

          <div id="bank-hint"></div>

          <button class="btn btn-primary btn-lg btn-block" id="run-check" disabled>${icon("bolt")}Check payments</button>
        </section>

        <aside class="stack">
          <div class="card card-pad">
            <h2>What to add</h2>
            <p class="sub">The more you add, the clearer the answer.</p>
            <div class="kinds mt-16">
              <div class="kind-card must">${icon("account_balance")}<b>Bank statement</b><span>CSV export from your bank. This is the proof.</span></div>
              <div class="kind-card">${icon("receipt_long")}<b>Invoices</b><span>PDF bills you sent or received.</span></div>
              <div class="kind-card">${icon("smartphone")}<b>Screenshots</b><span>GPay, PhonePe, Paytm payment screens.</span></div>
              <div class="kind-card">${icon("chat")}<b>Chats</b><span>WhatsApp/SMS export (.txt) or pasted text.</span></div>
            </div>
          </div>
          <div class="callout tone-gray">${icon("lock")}<span>Files are processed and then deleted. Only the results are saved to your private workspace.</span></div>
        </aside>
      </div>
    </div>`;

  const input = $("#file-input");
  const dz = $("#dz");
  const paste = $("#paste");
  paste.value = state.draftText;

  const refresh = () => {
    $("#file-list").innerHTML = state.draftFiles.map((f, i) => {
      const k = fileKind(f.name);
      return `
        <div class="file-item">
          <span class="ftype tone-${k.tone}">${icon(k.icon)}</span>
          <div style="flex:1;min-width:0">
            <div class="name">${esc(f.name)}</div>
            <div class="kind">${esc(k.label)}, ${fmtSize(f.size)}</div>
          </div>
          <button class="icon-btn" data-remove="${i}" aria-label="Remove ${esc(f.name)}">${icon("close")}</button>
        </div>`;
    }).join("");
    const hasBank = state.draftFiles.some((f) => fileKind(f.name).bank);
    const hasAny = state.draftFiles.length || paste.value.trim();
    $("#bank-hint").innerHTML = hasAny && !hasBank
      ? `<div class="callout tone-amber">${icon("info", "fill")}<span><b>Tip:</b> add your bank statement (CSV) too. Without it FinSync can read the claims but can't confirm that money actually arrived.</span></div>`
      : "";
    $("#run-check").disabled = !hasAny;
  };

  const addFiles = (list) => {
    for (const f of list) {
      const ext = (f.name.match(/\.[^.]+$/)?.[0] || "").toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) { toast(`${f.name}: this file type isn't supported.`, "error"); continue; }
      if (f.size > MAX_UPLOAD_MB * 1024 * 1024) { toast(`${f.name} is larger than ${MAX_UPLOAD_MB} MB.`, "error"); continue; }
      if (state.draftFiles.some((d) => d.name === f.name && d.size === f.size)) continue;
      state.draftFiles.push(f);
    }
    refresh();
  };

  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
  $("#file-list").addEventListener("click", (e) => {
    const i = e.target.closest("[data-remove]")?.dataset.remove;
    if (i !== undefined) { state.draftFiles.splice(Number(i), 1); refresh(); }
  });
  paste.addEventListener("input", () => { state.draftText = paste.value; refresh(); });
  $("#run-check").addEventListener("click", runCheck);
  refresh();
}

async function runCheck() {
  const text = state.draftText.trim();
  const form = new FormData();
  state.draftFiles.forEach((f) => form.append("files", f, f.name));
  if (text) form.append("files", new Blob([text], { type: "text/plain" }), "pasted_message.txt");
  if (![...form.keys()].length) return;

  const overlay = document.createElement("div");
  overlay.className = "processing";
  const steps = ["Reading your files", "Finding amounts and names", "Matching with your bank", "Looking for problems"];
  overlay.innerHTML = `
    <div class="card box" role="alertdialog" aria-live="polite" aria-label="Checking payments">
      <div class="spinner"></div>
      <h2>Checking your payments…</h2>
      <ol class="proc-steps">${steps.map((s) => `<li><span class="dot">${icon("radio_button_unchecked")}</span>${s}</li>`).join("")}</ol>
    </div>`;
  document.body.appendChild(overlay);
  const lis = $$(".proc-steps li", overlay);
  let i = 0;
  const tick = () => {
    lis.forEach((li, j) => {
      li.className = j < i ? "done" : j === i ? "on" : "";
      $(".dot", li).innerHTML = icon(j < i ? "check" : j === i ? "more_horiz" : "radio_button_unchecked");
    });
  };
  tick();
  const timer = setInterval(() => { if (i < steps.length - 1) { i++; tick(); } }, 650);
  const minWait = new Promise((r) => setTimeout(r, 1800));

  try {
    const [res] = await Promise.all([api("/api/v1/cases/files", { method: "POST", form }), minWait]);
    i = steps.length; tick();
    await new Promise((r) => setTimeout(r, 350));
    state.draftFiles = [];
    state.draftText = "";
    invalidateChecks();
    location.hash = `#/checks/${encodeURIComponent(res.case_id)}`;
  } catch (err) {
    toast(err.message, "error");
  } finally {
    clearInterval(timer);
    overlay.remove();
  }
}

/* ---------------------------------------------------------
   Checks list
   --------------------------------------------------------- */
const FILTERS = [
  { id: "all", label: "All", test: () => true },
  { id: "review", label: "Needs review", test: needsAttention },
  { id: "matched", label: "Matched", test: (c) => c.status === "CONFIRMED" },
  { id: "due", label: "Money due", test: (c) => (c.outstanding_amount || 0) > 0 },
  { id: "problems", label: "Mismatch", test: (c) => ["CONTRADICTED", "AMBIGUOUS"].includes(c.status) || c.issues_count > 0 },
];

async function viewChecks(view, query) {
  view.innerHTML = loadingState();
  const checks = await loadChecks(true);
  let filter = query.get("filter") || "all";
  let q = "";

  view.innerHTML = `
    <div class="page">
      <div class="page-head">
        <div><h1>Checks</h1><p>Every check you've run, newest first.</p></div>
        <a class="btn btn-primary hide-mobile" href="#/new">${icon("add")}New check</a>
      </div>
      ${checks.length ? `
        <div class="stack" style="gap:12px;margin-bottom:16px">
          <label class="search"><span class="sr-only">Search checks</span>${icon("search")}<input class="input" id="q" placeholder="Search by name or title"></label>
          <div class="chips" role="group" aria-label="Filter">${FILTERS.map((f) => `<button class="chip" data-f="${f.id}">${f.label}<span class="count">${checks.filter(f.test).length}</span></button>`).join("")}</div>
        </div>
        <div class="card" id="list-card"></div>` : `
        <div class="card empty">
          <div class="art">${icon("fact_check")}</div>
          <h3>No checks yet</h3>
          <p>When you run a check it shows up here with a clear verdict — Matched, Part paid or Mismatch.</p>
          <a class="btn btn-primary btn-lg" href="#/new">${icon("add")}Start your first check</a>
        </div>`}
    </div>`;
  if (!checks.length) return;

  const draw = () => {
    const f = FILTERS.find((x) => x.id === filter) || FILTERS[0];
    const ql = q.toLowerCase();
    const rows = checks.filter(f.test).filter((c) => !ql || `${c.counterparty || ""} ${c.title}`.toLowerCase().includes(ql));
    $$(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.f === filter)));
    $("#list-card").innerHTML = rows.length
      ? `<ul class="list">${rows.map(checkRow).join("")}</ul>`
      : `<div class="empty"><h3>Nothing here</h3><p>No checks match this filter.</p></div>`;
  };
  $$(".chip").forEach((c) => c.addEventListener("click", () => { filter = c.dataset.f; draw(); }));
  $("#q").addEventListener("input", debounce((e) => { q = e.target.value.trim(); draw(); }, 120));
  draw();
}

/* ---------------------------------------------------------
   One check
   --------------------------------------------------------- */
const TABS = [
  { id: "summary", label: "Summary", icon: "summarize" },
  { id: "records", label: "Records", icon: "folder_open" },
  { id: "review", label: "Your answer", icon: "rate_review" },
  { id: "followups", label: "Follow-ups", icon: "outgoing_mail" },
  { id: "history", label: "History", icon: "history" },
];

const caseCache = new Map(); // case_id -> { result, review }

async function viewCheck(view, id, tab) {
  const cached = caseCache.get(id);
  if (!cached) view.innerHTML = loadingState();

  const [result, review] = await Promise.all([
    api(`/api/v1/cases/${encodeURIComponent(id)}`),
    api(`/api/v1/cases/${encodeURIComponent(id)}/review`),
  ]);
  caseCache.set(id, { result, review });
  const r = result.truth_report || {};
  const recon = r.reconciliation_summary || {};
  const fs = result.financial_summary || {};
  const expected = recon.expected_amount ?? fs.claimed_amount;
  const matched = recon.matched_amount ?? fs.matched_amount;
  const due = recon.outstanding_amount ?? fs.outstanding_amount;
  const who = knownName(r.entity_summary?.canonical_name);
  const issues = r.contradiction_summary || [];
  const pendingReview = result.requires_review && !["RESOLVED", "CLOSED"].includes(review.status);
  const conf = Math.round((result.confidence || 0) * 100);
  const bannerQ = reviewQuestion(result.status, { who: who || "this person", expected, matched, due, issues, hasBank: (r.transaction_summary || []).length > 0 });

  view.innerHTML = `
    <div class="page">
      <a class="back-link" href="#/checks">${icon("arrow_back")}All checks</a>

      <section class="verdict" data-tour="verdict">
        <div class="verdict-top">
          <div class="who">
            <span class="avatar lg">${esc(initials(who || "?"))}</span>
            <div><h1>${esc(who || (result.status === "UNMATCHED" ? "Unknown payer" : "Payment check"))}</h1><span class="muted small">${esc(fmtDate(r.created_at, true))}</span></div>
          </div>
          ${statusPill(result.status, true)}
        </div>

        <div class="settle" data-tour="amounts">
          <p class="settle-figure"><span class="money">${inr(matched)}</span>${expected != null && expected !== matched ? `<span class="of">of ${inr(expected)}</span>` : ""}</p>
          <p class="settle-caption">${esc(plainSummary(result, r, who))}</p>
          ${expected && result.status !== "CONTRADICTED" ? `
          <div class="settle-bar" role="img" aria-label="${inr(matched)} received, ${inr(due)} still due">
            <span class="got" style="width:${Math.min(100, Math.round((matched / expected) * 100))}%"></span>
          </div>` : ""}
          <dl class="settle-legend">
            <div><dt><i class="sw got"></i>In your bank</dt><dd>${inr(matched)}</dd></div>
            ${result.status === "CONTRADICTED"
              ? `<div><dt>Status</dt><dd class="t-red">On hold until you answer</dd></div>`
              : `<div><dt><i class="sw due"></i>Still due</dt><dd>${inr(due)}</dd></div>`}
            <div><dt>Confidence</dt><dd>${conf}%</dd></div>
          </dl>
        </div>
        ${pendingReview ? `
          <div class="review-banner">
            ${icon("flag")}
            <div class="txt"><b>${esc(bannerQ.question)}</b>${esc(bannerQ.context)}</div>
            <a class="btn btn-primary btn-sm" href="#/checks/${encodeURIComponent(id)}?tab=review">Answer</a>
          </div>` : review.decision ? `
          <div class="callout tone-green">${icon("shield")}<span>Your answer: <b>${esc(DECISION_LABEL[review.decision] || titleCase(review.decision))}</b>. <a href="#/checks/${encodeURIComponent(id)}?tab=review" style="text-decoration:underline">View</a></span></div>` : ""}
      </section>

      <nav class="tabs" role="tablist" data-tour="tabs">
        ${TABS.map((t) => `<a class="tab" role="tab" aria-selected="${t.id === tab}" href="#/checks/${encodeURIComponent(id)}?tab=${t.id}">${icon(t.icon)}${t.label}${t.id === "summary" && issues.length ? `<span class="badge">${issues.length}</span>` : ""}${t.id === "review" && pendingReview ? `<span class="badge">!</span>` : ""}</a>`).join("")}
      </nav>

      <div id="tab-body"></div>
    </div>`;

  const body = $("#tab-body");
  const ctx = { id, result, review, report: r };
  if (tab === "records") renderRecordsTab(body, ctx);
  else if (tab === "review") renderReviewTab(body, ctx);
  else if (tab === "followups") await renderFollowupsTab(body, ctx);
  else if (tab === "history") await renderHistoryTab(body, ctx);
  else renderSummaryTab(body, ctx);
}

function knownName(n) {
  return n && !/^unknown/i.test(n.trim()) ? n : null;
}

function plainSummary(result, r, who) {
  const name = who || "this party";
  const fs = result.financial_summary || {};
  const recon = r.reconciliation_summary || {};
  const matched = recon.matched_amount ?? fs.matched_amount;
  const expected = recon.expected_amount ?? fs.claimed_amount;
  const due = recon.outstanding_amount ?? fs.outstanding_amount;
  switch (result.status) {
    case "CONFIRMED": return `The payment from ${name} is in your bank statement for the full amount.`;
    case "PARTIAL":
    case "PARTIALLY_SETTLED": return `${name} has paid part of it. ${inr(due)} is still due.`;
    case "CONTRADICTED": return `What was claimed for ${name} doesn't match your bank. Take a look before you mark it as paid.`;
    case "UNVERIFIABLE": return fs.transactions_count
      ? `We couldn't find a bank entry that proves the payment from ${name}.`
      : `No bank statement was included, so the payment from ${name} can't be confirmed yet. Add your bank statement in a new check.`;
    case "AMBIGUOUS": return `More than one bank entry could belong to ${name}. Please pick the right one.`;
    case "DUPLICATE": return `The same payment from ${name} appears more than once. It's counted only once.`;
    case "UNMATCHED": return `${inr(matched)} arrived in your bank, but nothing in your records explains who it's from or what it's for.`;
    default: return r.summary || "";
  }
}

function renderSummaryTab(body, { id, report: r }) {
  const issues = r.contradiction_summary || [];
  const unresolved = (r.unresolved_items || []).filter((u) => u.item_type !== "DISCREPANCY");
  const actions = r.recommended_actions || [];

  body.innerHTML = `
    <div class="grid-2">
      <div class="stack">
        <section class="card">
          <div class="card-pad" style="padding-bottom:6px">
            <h2>${issues.length || unresolved.length ? "What didn't add up" : "Nothing looks wrong"}</h2>
            <p class="sub">${issues.length || unresolved.length ? "Each item compares what was claimed with what your bank shows." : "Every claim we found lines up with your bank."}</p>
          </div>
          ${issues.length || unresolved.length ? `<div>${issues.map(issueHtml).join("")}${unresolved.map((u) => issueHtml({ discrepancy_type: u.item_type, severity: u.severity, message: u.description })).join("")}</div>` : `
            <div class="card-pad" style="padding-top:8px"><div class="callout tone-green">${icon("check_circle", "fill")}<span>No problems found.</span></div></div>`}
        </section>

        <section class="card card-pad">
          <h2>What to do next</h2>
          <ol class="todo list mt-12">
            ${actions.length ? actions.map((a, i) => `<li><span class="n">${i + 1}</span><span>${esc(a)}</span></li>`).join("") : `<li><span class="n">✓</span><span>Nothing to do right now.</span></li>`}
          </ol>
        </section>
      </div>

      <div class="stack">
        <section class="card card-pad" data-tour="ask">
          <h2>${icon("auto_awesome", "fill")} Ask about this check</h2>
          <p class="sub">Answers come only from your records — nothing is made up.</p>
          <form class="ask-form mt-16" id="ask-form">
            <label class="sr-only" for="ask-q">Your question</label>
            <input class="input" id="ask-q" placeholder="e.g. Why does this need review?" autocomplete="off">
            <button class="btn btn-primary" aria-label="Ask">${icon("arrow_upward")}</button>
          </form>
          <div class="suggest">
            ${["Why does this need review?", "What should I do next?", "How much is still due?", "Which bank entry matched?"].map((q) => `<button type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("")}
          </div>
          <div id="answers"></div>
        </section>

        <section class="card card-pad">
          <h2>In detail</h2>
          <p class="mt-8" style="color:var(--ink-2)">${esc(r.explanation || r.summary || "")}</p>
          ${(r.confidence_breakdown || []).length ? `
            <ul class="list mt-16" style="display:grid;gap:8px">
              ${r.confidence_breakdown.map((f) => `<li class="small" style="display:flex;gap:8px"><span class="${f.impact === "+" ? "in" : "out"}">${icon(f.impact === "+" ? "add_circle" : "remove_circle", "fill")}</span><span>${esc(f.description)}</span></li>`).join("")}
            </ul>` : ""}
        </section>
      </div>
    </div>`;

  const ask = async (question) => {
    if (!question) return;
    const box = $("#answers");
    const el = document.createElement("div");
    el.className = "answer";
    el.innerHTML = `<div class="q">${esc(question)}</div><div class="skeleton" style="height:16px;width:80%"></div>`;
    box.prepend(el);
    try {
      const res = await api(`/api/v1/cases/${encodeURIComponent(id)}/controller/explain`, { method: "POST", body: { question } });
      const answer = String(res.answer || "").replace(/\b[Cc]ase '[^']+'/g, "This check");
      el.innerHTML = `<div class="q">${esc(question)}</div>${esc(answer)}`;
    } catch (err) {
      el.innerHTML = `<div class="q">${esc(question)}</div>${esc(err.message)}`;
    }
  };
  $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#ask-q").value.trim(); $("#ask-q").value = ""; ask(q); });
  $$(".suggest button").forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));
}

function issueHtml(d) {
  const m = issueMeta(d.discrepancy_type);
  const sev = SEVERITY[d.severity] || { tone: "gray" };
  const hasCompare = d.expected_value && d.observed_value;
  return `
    <div class="issue">
      <span class="ico tone-${sev.tone}">${icon(m.icon)}</span>
      <div style="flex:1;min-width:0">
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center"><b>${esc(m.label)}</b>${severityPill(d.severity)}</div>
        <p>${esc(cleanMessage(d.message))}</p>
        ${hasCompare ? `<div class="compare"><span>Claimed: <b>${esc(fmtMaybeAmount(d.expected_value, d.discrepancy_type))}</b></span><span>Bank: <b>${esc(fmtMaybeAmount(d.observed_value, d.discrepancy_type))}</b></span></div>` : ""}
      </div>
    </div>`;
}
function cleanMessage(m) { return String(m || "").replace(/^[A-Z_]+:\s*/, "").replace(/\.\.$/, "."); }
function fmtMaybeAmount(v, type = "AMOUNT_MISMATCH") {
  return type === "AMOUNT_MISMATCH" && /^\d+(\.\d+)?$/.test(String(v)) ? inr(Number(v)) : String(v);
}
function possessive(name) { return /s$/i.test(name) ? `${name}'` : `${name}'s`; }

function renderRecordsTab(body, { report: r }) {
  const claims = r.claims_summary || [];
  const txns = r.transaction_summary || [];
  const evidence = r.evidence_summary || [];
  const groups = {};
  evidence.forEach((e) => {
    const file = String(e.source_name || "").split(":")[0] || "Pasted text";
    (groups[file] = groups[file] || { file, modality: e.modality, count: 0 }).count++;
  });

  body.innerHTML = `
    <div class="stack">
      <section class="card">
        <div class="card-pad" style="padding-bottom:10px">
          <h2>Bank entries</h2>
          <p class="sub">Real money movements from your bank statement — this is the proof.</p>
        </div>
        ${txns.length ? txns.map((t) => `
          <div class="rec">
            <span class="ico ${t.direction === "CREDIT" ? "tone-green" : "tone-red"}">${icon(t.direction === "CREDIT" ? "south_west" : "north_east")}</span>
            <div class="body">
              <b>${t.direction === "CREDIT" ? "Money in" : "Money out"}${t.payment_method ? ` via ${esc(t.payment_method)}` : ""}</b>
              <small>${esc(fmtDate(t.timestamp))}${t.bank_reference ? `<span class="ref">${esc(t.bank_reference)}</span>` : ""}</small>
            </div>
            <span class="amt ${t.direction === "CREDIT" ? "in" : "out"}">${t.direction === "CREDIT" ? "+" : "−"}${inr(t.amount)}</span>
          </div>`).join("") : `<div class="card-pad" style="padding-top:0"><div class="callout tone-amber">${icon("info", "fill")}<span>No bank statement was included in this check, so nothing could be confirmed. Run a new check with your bank statement CSV.</span></div></div>`}
      </section>

      <section class="card">
        <div class="card-pad" style="padding-bottom:10px">
          <h2>What people said or billed</h2>
          <p class="sub">Amounts found in invoices, screenshots and messages.</p>
        </div>
        ${claims.length ? claims.map((c) => {
          const m = CLAIM_TYPE[c.claim_type] || { label: titleCase(c.claim_type), icon: "description" };
          return `
          <div class="rec">
            <span class="ico tone-brand">${icon(m.icon)}</span>
            <div class="body">
              <b>${esc(c.counterparty_hint || "Unknown")}</b><small class="kind">${esc(m.label)}</small>
              <small>${esc(c.claimed_date || "No date")}${c.reference_id_hint ? `<span class="ref">${esc(c.reference_id_hint)}</span>` : ""}</small>
            </div>
            <span class="amt">${c.claimed_amount != null ? inr(c.claimed_amount) : `<span class="muted small">No amount</span>`}</span>
          </div>`;
        }).join("") : `<div class="card-pad" style="padding-top:0"><p class="muted">No claims were found in the files.</p></div>`}
      </section>

      <section class="card">
        <div class="card-pad" style="padding-bottom:10px">
          <h2>Files used</h2>
          <p class="sub">Each file is fingerprinted so any later change would be detected.</p>
        </div>
        ${Object.values(groups).map((g) => {
          const m = modalityMeta(g.modality);
          return `
          <div class="rec">
            <span class="ico tone-${m.tone}">${icon(m.icon)}</span>
            <div class="body"><b>${esc(g.file)}</b><small>${esc(m.label)}${g.count > 1 ? `, ${g.count} entries` : ""}</small></div>
          </div>`;
        }).join("") || `<div class="card-pad" style="padding-top:0"><p class="muted">No files.</p></div>`}
      </section>
    </div>`;
}

/* --- Review --- */
function reviewer() {
  return { reviewer_id: state.user?.id || "user", reviewer_name: state.user?.name || "You" };
}

async function ensureReviewStarted(id, review) {
  if (["PENDING", "NOT_REQUIRED"].includes(review.status)) {
    return api(`/api/v1/cases/${encodeURIComponent(id)}/review/start`, { method: "POST", body: reviewer() });
  }
  return review;
}

function renderReviewTab(body, { id, result, review, report: r }) {
  const closed = review.status === "CLOSED";
  const notes = review.notes || [];
  const rec = r.reconciliation_summary || {};
  const who = knownName(r.entity_summary?.canonical_name) || "this person";
  const expected = rec.expected_amount;
  const matched = rec.matched_amount || 0;
  const due = rec.outstanding_amount || 0;

  const allClaims = r.claims_summary || [];
  const allTxns = r.transaction_summary || [];
  const claims = (rec.claim_ids || []).length ? allClaims.filter((c) => rec.claim_ids.includes(c.claim_id)) : allClaims.slice(0, 1);
  const txns = allTxns.filter((t) => (rec.transaction_ids || []).includes(t.transaction_id));
  const issues = r.contradiction_summary || [];
  const evidenceById = Object.fromEntries((r.evidence_summary || []).map((e) => [e.evidence_id, e]));

  const q = reviewQuestion(result.status, { who, expected, matched, due, issues, hasBank: allTxns.length > 0 });
  const bad = new Set(issues.map((d) => d.discrepancy_type));
  const flag = (type) => (bad.has(type) ? ' class="conflict"' : "");

  const claimRow = (c) => {
    const ev = evidenceById[c.evidence_id];
    const src = ev ? modalityMeta(ev.modality).label : "Your records";
    return `
      <div class="cmp-item">
        <div class="cmp-amt money${bad.has("AMOUNT_MISMATCH") ? " conflict" : ""}">${c.claimed_amount != null ? inr(c.claimed_amount) : "No amount"}</div>
        <dl class="cmp-meta">
          <div${flag("ENTITY_MISMATCH")}><dt>From</dt><dd>${esc(c.counterparty_hint || "Unknown")}</dd></div>
          <div${flag("DATE_MISMATCH")}><dt>Date</dt><dd>${esc(fmtClaimDate(c.claimed_date))}</dd></div>
          ${c.reference_id_hint ? `<div${flag("REFERENCE_MISMATCH")}><dt>Reference</dt><dd class="mono">${esc(c.reference_id_hint)}</dd></div>` : ""}
          <div><dt>Source</dt><dd>${esc(src)}</dd></div>
        </dl>
      </div>`;
  };
  const txnRow = (t) => `
      <div class="cmp-item">
        <div class="cmp-amt money ${t.direction === "CREDIT" ? "in" : "out"}${bad.has("AMOUNT_MISMATCH") ? " conflict" : ""}">${t.direction === "CREDIT" ? "" : "−"}${inr(t.amount)}</div>
        <dl class="cmp-meta">
          <div${flag("DIRECTION_MISMATCH")}><dt>Type</dt><dd>${t.direction === "CREDIT" ? "Money in" : "Money out"}${t.payment_method ? `, ${esc(t.payment_method)}` : ""}</dd></div>
          <div${flag("DATE_MISMATCH")}><dt>Date</dt><dd>${esc(fmtDate(t.timestamp))}</dd></div>
          ${t.bank_reference ? `<div${flag("REFERENCE_MISMATCH")}><dt>Reference</dt><dd class="mono">${esc(t.bank_reference)}</dd></div>` : ""}
        </dl>
      </div>`;

  const decided = review.decision && ["RESOLVED", "CLOSED", "IN_PROGRESS", "ESCALATED"].includes(review.status);
  const chosen = decided ? q.options.find((o) => o.decision === review.decision) : null;

  body.innerHTML = `
    <div class="stack">
      <section class="card review-ask">
        <div class="card-pad">
          <h2 class="review-q">${esc(q.question)}</h2>
          <p class="sub" style="font-size:14.5px">${esc(q.context)}</p>
        </div>

        <div class="compare">
          <div class="cmp-col">
            <h3>${icon("chat")}What ${esc(who === "this person" ? "was claimed" : `${who} said`)}</h3>
            ${claims.length ? claims.map(claimRow).join("") : `<p class="cmp-empty">No claim found in your files.</p>`}
          </div>
          <div class="cmp-col">
            <h3>${icon("bank")}What your bank shows</h3>
            ${txns.length ? txns.map(txnRow).join("") : `<div class="cmp-empty">${icon("searchX")}<span>${allTxns.length ? "No matching entry in your bank statement." : "No bank statement was added to this check."}</span></div>`}
          </div>
        </div>

        ${q.gap ? `<div class="cmp-gap tone-${q.gapTone}">${icon(q.gapTone === "red" ? "alert" : "info")}<span>${q.gap}</span></div>` : ""}
      </section>

      ${chosen ? `
      <section class="card card-pad answered">
        <div class="answered-head">
          <span class="ico tone-${chosen.tone}">${icon(chosen.icon)}</span>
          <div>
            <p class="muted small">Your answer</p>
            <h2>${esc(chosen.label)}</h2>
          </div>
        </div>
        <p class="mt-12">${esc(chosen.next)}</p>
        <div class="row-actions mt-16">
          ${chosen.cta ? `<a class="btn btn-primary" href="#/checks/${encodeURIComponent(id)}?tab=followups">${icon(chosen.cta.icon)}${esc(chosen.cta.label)}</a>` : ""}
          ${closed ? "" : `<button class="btn btn-secondary" id="change-answer">Change answer</button>`}
          ${review.status === "RESOLVED" ? `<button class="btn btn-ghost" id="close-review">${icon("lock")}Close this check</button>` : ""}
        </div>
        ${closed ? `<div class="callout tone-gray mt-16">${icon("lock")}<span>This check is closed and locked.</span></div>` : ""}
      </section>` : `
      <section class="card card-pad" id="answer-card">
        <h2>Your answer</h2>
        <p class="sub">Pick the one that fits. Your answer is saved with this check; it doesn't change the bank figures.</p>
        <div class="answers mt-16" role="radiogroup" aria-label="Your answer">
          ${q.options.map((o, i) => `
            <label class="answer-opt">
              <input type="radio" name="answer" value="${i}">
              <span class="ico tone-${o.tone}">${icon(o.icon)}</span>
              <span class="txt"><b>${esc(o.label)}</b><span>${esc(o.hint)}</span></span>
            </label>`).join("")}
        </div>
        <div class="field mt-16">
          <label for="answer-note">Add a note <span class="muted" style="font-weight:400">(optional)</span></label>
          <textarea class="textarea" id="answer-note" maxlength="2000" style="min-height:76px" placeholder="${esc(q.notePlaceholder || "Anything you want to remember about this check")}"></textarea>
        </div>
        <div class="mt-16"><button class="btn btn-primary btn-lg" id="save-answer" disabled>Save answer</button></div>
      </section>`}

      <section class="card">
        <div class="card-pad" ${notes.length ? 'style="padding-bottom:12px"' : ""}>
          <h2>Notes</h2>
          <p class="sub">Time-stamped and permanent, handy for your accountant.</p>
          ${closed || !chosen ? "" : `
          <form id="note-form" class="stack mt-16" style="gap:10px">
            <label class="sr-only" for="note">Add a note</label>
            <textarea class="textarea" id="note" maxlength="2000" style="min-height:76px" placeholder="Write a note"></textarea>
            <div><button class="btn btn-secondary btn-sm">${icon("plus")}Add note</button></div>
          </form>`}
          ${!notes.length ? `<p class="muted small mt-12">No notes yet.</p>` : ""}
        </div>
        ${notes.slice().reverse().map((n) => {
          const m = String(n.content).match(/^\[DECISION: (\w+)\]\s*/);
          const text = m ? n.content.slice(m[0].length) : n.content;
          const tag = m ? `, with answer "${esc(DECISION_LABEL[m[1]] || titleCase(m[1]))}"` : "";
          return `<div class="note"><div class="who">${esc(n.reviewer_name || "You")}, ${esc(fmtDate(n.timestamp, true))}${tag}</div><p>${esc(text)}</p></div>`;
        }).join("")}
      </section>
    </div>`;

  const busy = (on) => $$("button, input, textarea", body).forEach((el) => { el.disabled = on; });

  $$('input[name="answer"]', body).forEach((radio) => radio.addEventListener("change", () => {
    $$(".answer-opt", body).forEach((l) => l.classList.toggle("selected", l.contains(radio) && radio.checked));
    $("#save-answer").disabled = false;
  }));

  $("#save-answer")?.addEventListener("click", async () => {
    const picked = $('input[name="answer"]:checked', body);
    if (!picked) return;
    const opt = q.options[Number(picked.value)];
    const note = $("#answer-note").value.trim();
    busy(true);
    try {
      let rv = await ensureReviewStarted(id, review);
      if (rv.status === "RESOLVED") rv = await api(`/api/v1/cases/${encodeURIComponent(id)}/review/start`, { method: "POST", body: reviewer() });
      await api(`/api/v1/cases/${encodeURIComponent(id)}/review/decision`, { method: "POST", body: { decision: opt.decision, notes: note || undefined, ...reviewer() } });
      if (opt.decision !== "NEEDS_MORE_EVIDENCE") {
        await api(`/api/v1/cases/${encodeURIComponent(id)}/review/resolve`, { method: "POST", body: reviewer() });
      }
      invalidateChecks();
      toast("Answer saved.", "success");
      render();
    } catch (err) {
      toast(err.message, "error");
      busy(false);
    }
  });

  $("#change-answer")?.addEventListener("click", () => {
    review.decision = null;
    renderReviewTab(body, { id, result, review, report: r });
  });

  $("#note-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const content = $("#note").value.trim();
    if (!content) return;
    busy(true);
    try {
      await api(`/api/v1/cases/${encodeURIComponent(id)}/review/note`, { method: "POST", body: { content, ...reviewer() } });
      toast("Note saved.", "success");
      render();
    } catch (err) {
      toast(err.message, "error");
      busy(false);
    }
  });

  $("#close-review")?.addEventListener("click", async () => {
    const ok = await confirmDialog({ title: "Close this check?", body: "Closed checks are locked. You won't be able to change your answer or add notes.", confirm: "Close check" });
    if (!ok) return;
    try {
      await api(`/api/v1/cases/${encodeURIComponent(id)}/review/close`, { method: "POST", body: reviewer() });
      invalidateChecks();
      toast("Check closed.", "success");
      render();
    } catch (err) { toast(err.message, "error"); }
  });
}

function fmtClaimDate(v) {
  if (!v) return "Not stated";
  const m = String(v).match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  return m ? fmtDate(`${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`) : String(v);
}

/* The question, context and answers shown on the Review tab, in plain words per situation. */
function reviewQuestion(status, { who, expected, matched, due, issues, hasBank }) {
  const first = who === "this person" ? "they" : who.split(" ")[0];
  const later = { decision: "NEEDS_MORE_EVIDENCE", icon: "hourglass", tone: "gray", label: "Not sure yet, keep it open",
    hint: "Come back after you get more proof or a newer statement.",
    next: "This check stays open. Run a new check when you have a newer bank statement or more proof." };

  if (status === "PARTIAL" || status === "PARTIALLY_SETTLED") {
    return {
      question: `Did ${who} pay you only ${inr(matched)}?`,
      context: `${who} claims ${inr(expected)}, but your bank shows ${inr(matched)}. ${inr(due)} is missing.`,
      gap: `<b>${inr(due)} short.</b> The bank entry is real, but it's less than what was claimed.`, gapTone: "amber",
      notePlaceholder: `e.g. Called ${first}, the rest comes on Friday.`,
      options: [
        { decision: "CONFIRMED", icon: "check", tone: "green", label: `Yes, ${first} still owes ${inr(due)}`,
          hint: `Accept the ${inr(matched)} as received and follow up for the rest.`,
          next: `Got it: ${inr(matched)} is accepted and ${inr(due)} is still owed. Send ${first} a reminder for the balance.`,
          cta: { label: "Send a payment reminder", icon: "bell" } },
        { decision: "ACKNOWLEDGED", icon: "checkCircle", tone: "blue", label: "The rest was paid another way",
          hint: "e.g. cash, a different account, or a discount you agreed to.",
          next: "Noted: you've confirmed the full amount is settled outside this bank statement. Add a note so you remember how." },
        { ...later },
      ],
    };
  }
  if (status === "UNVERIFIABLE") {
    return {
      question: hasBank ? `Did ${possessive(who)} ${inr(expected)} reach you?` : `Can you confirm ${possessive(who)} payment?`,
      context: hasBank
        ? `${who} says they paid ${inr(expected)}, but there's no matching entry in the bank statement you added.`
        : "This check has no bank statement, so FinSync couldn't look for the money.",
      gap: hasBank ? `<b>${inr(expected)} not found</b> in your bank statement.` : "<b>No bank statement.</b> Add one in a new check to confirm automatically.", gapTone: "red",
      options: [
        { decision: "REJECTED", icon: "x", tone: "red", label: "No, it never arrived",
          hint: `Ask ${first} for proof such as a UTR number or bank receipt.`,
          next: `Marked as not received. Ask ${first} for proof of payment, like a UTR number or a bank receipt.`,
          cta: { label: "Ask for proof", icon: "fileSearch" } },
        { decision: "ACKNOWLEDGED", icon: "checkCircle", tone: "green", label: "Yes, I got it another way",
          hint: "e.g. cash, or into an account that isn't in this statement.",
          next: "Noted: you've confirmed the payment arrived outside this statement. Add a note saying where." },
        { ...later, label: "I'll check a newer statement", hint: "The money might not show up in this statement yet." },
      ],
    };
  }
  if (status === "CONTRADICTED") {
    const issue = issues[0];
    const what = issue ? issueMeta(issue.discrepancy_type).label.toLowerCase() : "details don't match";
    const detail = issue && issue.expected_value && issue.observed_value
      ? `${who} gave <b>${esc(fmtMaybeAmount(issue.expected_value, issue.discrepancy_type))}</b>, your bank shows <b>${esc(fmtMaybeAmount(issue.observed_value, issue.discrepancy_type))}</b>.`
      : esc(cleanMessage(issue?.message || "The claim and the bank entry disagree."));
    return {
      question: `Is ${possessive(who)} payment genuine?`,
      context: `The amount lines up, but the ${what}. That can be a typo, or a sign the proof isn't real.`,
      gap: `<b>${esc(issue ? issueMeta(issue.discrepancy_type).label : "Mismatch")}.</b> ${detail}`, gapTone: "red",
      notePlaceholder: `e.g. ${first === "they" ? "They" : first} sent a screenshot with the correct UTR.`,
      options: [
        { decision: "CONFIRMED", icon: "check", tone: "green", label: "Yes, it's a genuine payment",
          hint: "The difference is a typo or a harmless mix-up.",
          next: "Marked as genuine. The payment counts as received." },
        { decision: "REJECTED", icon: "alert", tone: "red", label: "No, something's wrong",
          hint: "The proof doesn't match. Raise it with them.",
          next: `Marked as wrong. Send ${first} a notice pointing out the mismatch.`,
          cta: { label: "Draft a dispute notice", icon: "scale" } },
        { ...later },
      ],
    };
  }
  if (status === "UNMATCHED") {
    return {
      question: `Do you know who sent ${inr(matched)}?`,
      context: "This money is in your bank, but nothing in your files says who it's from or what it's for.",
      gap: null,
      options: [
        { decision: "ACKNOWLEDGED", icon: "checkCircle", tone: "green", label: "Yes, I know what it's for",
          hint: "Add a note with who sent it, so your books are complete.",
          next: "Noted. Make sure the note says who sent it and why." },
        { ...later, label: "No idea yet", hint: "Keep it open until you find out." },
      ],
    };
  }
  if (status === "AMBIGUOUS" || status === "DUPLICATE") {
    return {
      question: status === "DUPLICATE" ? "Is this the same payment twice?" : `Which payment is ${possessive(who)}?`,
      context: status === "DUPLICATE" ? "The same payment shows up more than once in your files. FinSync counts it once." : "More than one bank entry could belong to this claim.",
      gap: null,
      options: [
        { decision: "CONFIRMED", icon: "check", tone: "green", label: "Looks right", hint: "Accept what FinSync found.", next: "Accepted." },
        { decision: "REJECTED", icon: "x", tone: "red", label: "Something's wrong", hint: "Flag it and follow up.", next: "Marked as wrong. Follow up with them." },
        { ...later },
      ],
    };
  }
  return {
    question: "Everything matched. Anything to add?",
    context: `The payment from ${who} is in your bank for the full amount. You don't need to do anything.`,
    gap: null,
    options: [
      { decision: "CONFIRMED", icon: "check", tone: "green", label: "Looks right", hint: "Mark it as checked by you.", next: "Marked as checked. Nothing else to do." },
      { decision: "REJECTED", icon: "x", tone: "red", label: "Something's wrong", hint: "You know something FinSync doesn't.", next: "Marked as wrong. Add a note explaining why." },
    ],
  };
}

/* --- Follow-ups --- */
const FOLLOWUPS = [
  { type: "PAYMENT_FOLLOWUP_DRAFT", icon: "notifications_active", title: "Payment reminder", sub: "Polite reminder for money still due." },
  { type: "VENDOR_DISPUTE_NOTICE", icon: "gavel", title: "Dispute notice", sub: "Point out a mismatch to the other party." },
  { type: "MISSING_EVIDENCE_REQUEST", icon: "find_in_page", title: "Ask for proof", sub: "Request a UTR, receipt or statement." },
  { type: "DRAFT_JOURNAL_VOUCHER", icon: "menu_book", title: "Accounting entry", sub: "Draft journal entry for your books." },
];
const APPROVAL = {
  DRAFT: { label: "Draft", tone: "gray" }, PENDING_APPROVAL: { label: "Waiting for approval", tone: "amber" },
  APPROVED: { label: "Approved", tone: "green" }, REJECTED: { label: "Discarded", tone: "gray" },
  EXECUTED: { label: "Done", tone: "green" },
};

async function renderFollowupsTab(body, { id }) {
  body.innerHTML = `<div class="skeleton" style="height:180px"></div>`;
  const actions = await api(`/api/v1/cases/${encodeURIComponent(id)}/actions`);

  body.innerHTML = `
    <div class="stack">
      <section class="card card-pad">
        <h2>Create a draft</h2>
        <p class="sub">FinSync writes it using only the facts in this check. Nothing is sent — you copy and send it yourself.</p>
        <div class="followup-grid mt-16">
          ${FOLLOWUPS.map((f) => `<button class="fu-card" data-type="${f.type}"><span class="ico">${icon(f.icon)}</span><b>${f.title}</b><span>${f.sub}</span></button>`).join("")}
        </div>
      </section>

      ${actions.length ? `<h2 class="section-title" style="margin-top:8px">Your drafts</h2>${actions.slice().reverse().map(draftHtml).join("")}` : `
        <div class="card empty" style="padding:28px 20px">
          <div class="art">${icon("outgoing_mail")}</div>
          <h3>No drafts yet</h3>
          <p>Pick one of the options above to create a reminder, notice or accounting entry.</p>
        </div>`}
    </div>`;

  $$(".fu-card", body).forEach((btn) => btn.addEventListener("click", async () => {
    $$(".fu-card", body).forEach((b) => (b.disabled = true));
    try {
      await api(`/api/v1/cases/${encodeURIComponent(id)}/actions/propose`, { method: "POST", body: { action_type: btn.dataset.type } });
      toast("Draft created.", "success");
      render();
    } catch (err) {
      toast(err.message, "error");
      $$(".fu-card", body).forEach((b) => (b.disabled = false));
    }
  }));

  body.addEventListener("click", async (e) => {
    const el = e.target.closest("[data-draft-act]");
    if (!el) return;
    const { draftAct, aid } = el.dataset;
    if (draftAct === "download") {
      const action = actions.find((x) => x.action_id === aid);
      const blob = new Blob([JSON.stringify(action?.journal_voucher || {}, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = Object.assign(document.createElement("a"), { href: url, download: `${id}_journal_entry.json` });
      link.click();
      URL.revokeObjectURL(url);
      return;
    }
    if (draftAct === "copy") {
      const text = $(`#draft-text-${CSS.escape(aid)}`)?.innerText || "";
      try { await navigator.clipboard.writeText(text); toast("Copied to clipboard.", "success"); }
      catch { toast("Couldn't copy. Select the text and copy it manually.", "error"); }
      return;
    }
    el.disabled = true;
    try {
      const path = draftAct === "approve" ? "approve" : "reject";
      await api(`/api/v1/cases/${encodeURIComponent(id)}/actions/${encodeURIComponent(aid)}/${path}`, {
        method: "POST", body: { reviewer_id: state.user?.id || "user", reason: "Not needed" },
      });
      toast(draftAct === "approve" ? "Approved." : "Discarded.", "success");
      render();
    } catch (err) { toast(err.message, "error"); el.disabled = false; }
  });
}

function draftHtml(a) {
  const st = APPROVAL[a.approval_status] || { label: titleCase(a.approval_status), tone: "gray" };
  const meta = FOLLOWUPS.find((f) => f.type === a.action_type);
  const pending = ["DRAFT", "PENDING_APPROVAL"].includes(a.approval_status);
  let content = "";
  if (a.notice_draft) {
    const n = a.notice_draft;
    const noId = (t) => String(t || "").replace(/\s*[—-]\s*Case\s+\S+/g, "").replace(/\s+for Case\s+\S+/g, "");
    content = `<div class="subj">${esc(noId(n.subject))}</div><pre id="draft-text-${esc(a.action_id)}">${esc(noId(n.subject))}\n\n${esc(noId(n.body))}</pre>`;
  } else if (a.journal_voucher) {
    const v = a.journal_voucher;
    content = `
      <div class="table-wrap">
        <table class="t" id="draft-text-${esc(a.action_id)}">
          <thead><tr><th>Account</th><th class="num">Debit</th><th class="num">Credit</th></tr></thead>
          <tbody>${(v.lines || []).map((l) => `<tr><td>${esc(l.account_name)}<div class="muted">${esc(l.narration || "")}</div></td><td class="num">${l.debit_amount ? inr(l.debit_amount) : ""}</td><td class="num">${l.credit_amount ? inr(l.credit_amount) : ""}</td></tr>`).join("")}</tbody>
          <tfoot><tr><td><b>Total</b>${v.is_balanced ? ` <span class="pill tone-green">Balanced</span>` : ""}</td><td class="num">${inr(v.total_debits)}</td><td class="num">${inr(v.total_credits)}</td></tr></tfoot>
        </table>
      </div>
      <p class="muted small mt-12">Account names are placeholders — map them to your own chart of accounts before posting.</p>`;
  } else {
    content = `<p id="draft-text-${esc(a.action_id)}">${esc(a.summary || "")}</p>`;
  }
  return `
    <article class="draft">
      <div class="draft-head">
        <div style="display:flex;gap:10px;align-items:center">${icon(meta?.icon || "draft")}<b>${esc(meta?.title || a.title)}</b></div>
        <span class="pill tone-${st.tone}">${esc(st.label)}</span>
      </div>
      <div class="draft-body">${content}</div>
      <div class="draft-actions">
        <button class="btn btn-secondary btn-sm" data-draft-act="copy" data-aid="${esc(a.action_id)}">${icon("content_copy")}Copy</button>
        ${a.journal_voucher ? `<button class="btn btn-secondary btn-sm" data-draft-act="download" data-aid="${esc(a.action_id)}">${icon("download")}Download</button>` : ""}
        ${pending ? `
          <button class="btn btn-success btn-sm" data-draft-act="approve" data-aid="${esc(a.action_id)}">${icon("check")}Approve</button>
          <button class="btn btn-ghost btn-sm" data-draft-act="reject" data-aid="${esc(a.action_id)}">Discard</button>` : ""}
      </div>
    </article>`;
}

/* --- History --- */
const EVENT_LABEL = {
  REVIEW_CREATED: { label: "Check created", icon: "add_circle" },
  REVIEW_STARTED: { label: "Review started", icon: "play_circle" },
  NOTE_ADDED: { label: "Note added", icon: "sticky_note_2" },
  EVIDENCE_REVIEWED: { label: "Record inspected", icon: "visibility" },
  ACTION_CREATED: { label: "Task added", icon: "add_task" },
  ACTION_COMPLETED: { label: "Task done", icon: "task_alt" },
  DECISION_RECORDED: { label: "Decision recorded", icon: "gavel" },
  REVIEW_ESCALATED: { label: "Escalated", icon: "priority_high" },
  REVIEW_RESOLVED: { label: "Marked reviewed", icon: "verified" },
  REVIEW_CLOSED: { label: "Closed", icon: "lock" },
};

async function renderHistoryTab(body, { id }) {
  body.innerHTML = `<div class="skeleton" style="height:180px"></div>`;
  const events = await api(`/api/v1/cases/${encodeURIComponent(id)}/review/audit`);
  body.innerHTML = `
    <div class="stack">
      <section class="card card-pad">
        <div class="card-head">
          <div><h2>Activity</h2><p class="sub">Every change is recorded and chained together, so history can't be quietly edited.</p></div>
        </div>
        <ul class="timeline">
          ${events.slice().reverse().map((e) => {
            const m = EVENT_LABEL[e.event_type] || { label: titleCase(e.event_type), icon: "radio_button_checked" };
            return `<li><span class="dot">${icon(m.icon)}</span><b>${esc(m.label)}</b><small>${esc(fmtDate(e.timestamp, true))}, ${esc(e.actor_id === "system" ? "FinSync" : e.actor_id === state.user?.id ? "You" : e.actor_id)}</small><p>${esc(e.description)}</p></li>`;
          }).join("") || `<li><p class="muted">No activity yet.</p></li>`}
        </ul>
        <div class="row-actions mt-8">
          <button class="btn btn-secondary btn-sm" id="verify">${icon("verified_user")}Verify history is untouched</button>
          <span id="verify-out" class="small" style="align-self:center"></span>
        </div>
      </section>

      <section class="card card-pad">
        <h2 style="color:var(--red)">Delete this check</h2>
        <p class="sub">Removes the check and its results from your workspace. This can't be undone.</p>
        <div class="mt-16"><button class="btn btn-danger" id="delete-check">${icon("delete")}Delete check</button></div>
      </section>
    </div>`;

  $("#verify").addEventListener("click", async () => {
    try {
      const res = await api(`/api/v1/cases/${encodeURIComponent(id)}/review/audit/verify`);
      const ok = res.is_valid ?? res.valid ?? res.chain_valid;
      $("#verify-out").innerHTML = ok
        ? `<span class="pill tone-green">${icon("check_circle", "fill")}All ${res.event_count ?? res.total_events ?? events.length} entries verified</span>`
        : `<span class="pill tone-red">${icon("error", "fill")}History has been changed</span>`;
    } catch (err) { toast(err.message, "error"); }
  });

  $("#delete-check").addEventListener("click", async () => {
    const ok = await confirmDialog({ title: "Delete this check?", body: "The results, review and notes for this check will be permanently removed.", confirm: "Delete", danger: true });
    if (!ok) return;
    try {
      await api(`/api/v1/checks/${encodeURIComponent(id)}`, { method: "DELETE" });
      caseCache.delete(id);
      invalidateChecks();
      toast("Check deleted.", "success");
      location.hash = "#/checks";
    } catch (err) { toast(err.message, "error"); }
  });
}

/* ---------------------------------------------------------
   People
   --------------------------------------------------------- */
async function viewPeople(view) {
  view.innerHTML = loadingState();
  const people = await api("/api/v1/counterparties");
  view.innerHTML = `
    <div class="page">
      <div class="page-head"><div><h1>People</h1><p>Customers and vendors FinSync found across your checks.</p></div></div>
      ${people.length ? `
        <div class="people-grid">
          ${people.map((p) => `
            <a class="card person" href="#/people/${encodeURIComponent(p.name)}">
              <div class="who">
                <span class="avatar">${esc(initials(p.name))}</span>
                <span style="min-width:0"><b>${esc(p.name)}</b><small>${p.checks} check${p.checks === 1 ? "" : "s"}, last ${esc(relTime(p.last_seen)).toLowerCase()}</small></span>
              </div>
              <div class="nums">
                <div><small>In your bank</small><b class="in">${inr(p.matched_amount)}</b></div>
                <div><small>Still due</small><b style="color:${p.outstanding_amount > 0 ? "var(--amber)" : "inherit"}">${inr(p.outstanding_amount)}</b></div>
              </div>
            </a>`).join("")}
        </div>` : `
        <div class="card empty">
          <div class="art">${icon("group")}</div>
          <h3>No one here yet</h3>
          <p>As you run checks, FinSync remembers each customer and vendor — so you can see who has paid and who still owes you.</p>
          <a class="btn btn-primary btn-lg" href="#/new">${icon("add")}Start a check</a>
        </div>`}
    </div>`;
}

async function viewPerson(view, name) {
  view.innerHTML = loadingState();
  const [people, checks] = await Promise.all([api("/api/v1/counterparties"), loadChecks(true)]);
  const p = people.find((x) => x.name.toLowerCase() === name.toLowerCase());
  if (!p) { view.innerHTML = errorState(new Error("This person isn't in any of your checks anymore.")); return; }
  const theirs = checks.filter((c) => p.case_ids.includes(c.case_id));
  view.innerHTML = `
    <div class="page">
      <a class="back-link" href="#/people">${icon("arrow_back")}People</a>
      <div class="page-head" style="align-items:center">
        <div style="display:flex;gap:14px;align-items:center">
          <span class="avatar" style="width:56px;height:56px;font-size:20px">${esc(initials(p.name))}</span>
          <div><h1>${esc(p.name)}</h1><p>${p.checks} check${p.checks === 1 ? "" : "s"}</p></div>
        </div>
      </div>
      <div class="stats">
        <div class="card stat"><span class="label">Expected</span><span class="value">${inr(p.expected_amount)}</span></div>
        <div class="card stat"><span class="label">In your bank</span><span class="value in">${inr(p.matched_amount)}</span></div>
        <div class="card stat"><span class="label">Still due</span><span class="value" style="color:var(--amber)">${inr(p.outstanding_amount)}</span></div>
        <div class="card stat"><span class="label">Issues found</span><span class="value">${p.issues_count}</span></div>
      </div>
      <h2 class="section-title">Checks</h2>
      <div class="card"><ul class="list">${theirs.map(checkRow).join("")}</ul></div>
    </div>`;
}

/* ---------------------------------------------------------
   Help
   --------------------------------------------------------- */
function viewHelp(view) {
  const order = ["CONFIRMED", "PARTIAL", "CONTRADICTED", "UNVERIFIABLE", "AMBIGUOUS", "DUPLICATE"];
  view.innerHTML = `
    <div class="page">
      <div class="page-head">
        <div><h1>How FinSync works</h1><p>Everything you need to know, in two minutes.</p></div>
        <button class="btn btn-secondary" id="tour-again">${icon("tour")}Take the tour</button>
      </div>

      <ol class="steps">
        <li><span class="num">1</span><div><h3>You add records</h3><p>Your bank statement (CSV) plus invoices, payment screenshots or chat messages.</p></div></li>
        <li><span class="num">2</span><div><h3>FinSync reads and matches</h3><p>It pulls out amounts, names, dates and UTR numbers, then looks for the matching bank entry.</p></div></li>
        <li><span class="num">3</span><div><h3>You get a verdict</h3><p>A clear status, the amount still due, any problems and suggested next steps.</p></div></li>
      </ol>

      <h2 class="section-title">What each status means</h2>
      <section class="card glossary">
        ${order.map((s) => `<div class="g">${statusPill(s)}<p>${esc(statusMeta(s).help)}</p></div>`).join("")}
      </section>

      <h2 class="section-title">Questions</h2>
      <section class="card faq">
        <details><summary>Why is the bank statement so important?</summary><p>A screenshot or a "payment done" message is just a claim. Only your bank statement proves money actually arrived. FinSync uses the statement as the source of truth and checks everything else against it.</p></details>
        <details><summary>Which bank statement format works?</summary><p>A CSV export from your net-banking (HDFC, ICICI, SBI, Axis and most others) or a Razorpay settlement report. Columns like Date, Narration, Ref No, Withdrawal and Deposit are recognised automatically.</p></details>
        <details><summary>What does "Review" mean?</summary><p>When something doesn't add up, FinSync asks you to decide. Approve it, mark it wrong, or keep it open until you get more proof. Your decision never changes the underlying numbers — it's recorded alongside them.</p></details>
        <details><summary>Does FinSync send emails for me?</summary><p>No. Follow-ups are drafts. You copy them and send them yourself from your email or WhatsApp.</p></details>
        <details><summary>Who can see my data?</summary><p>Only you. Every account has its own private workspace. Uploaded files are deleted right after processing; only the results are kept.</p></details>
      </section>
    </div>`;
  $("#tour-again").addEventListener("click", () => startTour("main", true));
}

/* ---------------------------------------------------------
   Account
   --------------------------------------------------------- */
function viewAccount(view, query) {
  const u = state.user;
  view.innerHTML = `
    <div class="page">
      <div class="page-head"><div><h1>Account</h1><p>Your profile and preferences.</p></div></div>
      <div class="stack">
        <section class="card card-pad" style="display:flex;gap:16px;align-items:center">
          <span class="avatar" style="width:60px;height:60px;font-size:22px">${esc(initials(u.name))}</span>
          <div style="min-width:0">
            <h2>${esc(u.name)}</h2>
            <p class="sub">${esc(u.email || "Local workspace (no sign-in configured)")}</p>
          </div>
        </section>

        <section class="card card-pad">
          <div class="card-head" style="margin:0;align-items:center">
            <div><h2>Appearance</h2><p class="sub">Light, dark, or match your device.</p></div>
            ${themeToggleHtml()}
          </div>
        </section>

        ${state.authEnabled ? `
        <section class="card card-pad" id="pw-card">
          <h2>Change password</h2>
          <p class="sub">After changing it, we'll email you a confirmation.</p>
          <form id="pw-form" class="stack mt-16" style="max-width:420px" novalidate>
            ${fieldHtml({ id: "new-pw", label: "New password", type: "password", max: LIMITS.pwMax, auto: "new-password", placeholder: "Create a strong password", hint: `<ul class="pw-rules" id="acc-rules">${pwChecklist("")}</ul>` })}
            <div><button class="btn btn-primary">Update password</button></div>
          </form>
        </section>` : ""}

        <section class="card">
          <ul class="list">
            <li><button class="row" id="acc-tour"><span class="ico">${icon("tour")}</span><span class="main-col"><span class="title">Replay the welcome tour</span><span class="meta">A quick walkthrough of each part of FinSync</span></span>${icon("chevron_right", "chev")}</button></li>
            <li><a class="row" href="#/help"><span class="ico">${icon("lightbulb")}</span><span class="main-col"><span class="title">How FinSync works</span><span class="meta">Statuses, file types and FAQs</span></span>${icon("chevron_right", "chev")}</a></li>
            ${state.authEnabled ? `<li><button class="row" id="acc-signout" style="color:var(--red)"><span class="ico">${icon("logout")}</span><span class="main-col"><span class="title">Sign out</span></span></button></li>` : ""}
          </ul>
        </section>
        <p class="muted small" style="text-align:center">FinSync, payment checks for Indian businesses</p>
      </div>
    </div>`;

  $("#acc-tour").addEventListener("click", () => { location.hash = "#/"; setTimeout(() => startTour("main", true), 300); });
  $("#acc-signout")?.addEventListener("click", () => signOut());
  wireReveal(view);
  $("#new-pw")?.addEventListener("input", (e) => { $("#acc-rules").innerHTML = pwChecklist(e.target.value); });
  $("#pw-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pw = $("#new-pw").value;
    const problem = validatePassword(pw);
    setFieldError("new-pw", problem);
    if (problem) return;
    const { error } = await state.sb.auth.updateUser({ password: pw });
    if (error) {
      const msg = /reauth|recent/i.test(error.message) ? "For your security, sign out and sign in again before changing your password." : friendlyAuthError(error);
      return toast(msg, "error");
    }
    $("#new-pw").value = "";
    $("#acc-rules").innerHTML = pwChecklist("");
    toast("Password updated.", "success");
  });
}

/* ---------------------------------------------------------
   Guided tour
   --------------------------------------------------------- */
const TOURS = {
  main: [
    { icon: "waving_hand", title: "Welcome to FinSync", body: "FinSync checks whether the payments people tell you about actually reached your bank. Here's a quick 30-second tour." },
    { target: "new", icon: "add_circle", title: "Start a new check", body: "Upload your bank statement together with invoices, payment screenshots or WhatsApp chats. FinSync matches every claim against your bank." },
    { target: "home", icon: "home", title: "Your dashboard", body: "See at a glance how much has been confirmed in your bank, what's still due, and which checks need you." },
    { target: "checks", icon: "fact_check", title: "All your checks", body: "Every check gets a plain verdict — Matched, Part paid, Mismatch or No bank proof. The red badge counts checks waiting for your review." },
    { target: "people", icon: "group", title: "Customers & vendors", body: "FinSync remembers everyone across your checks, so you can see who has paid and who still owes you." },
    { target: "help", icon: "lightbulb", title: "Help is always here", body: "Status meanings, supported files and FAQs. You can replay this tour from here or from Account anytime." },
    { icon: "rocket_launch", title: "You're all set!", body: "Your workspace starts empty — nothing is filled in for you. Run your first check whenever you're ready.", cta: { label: "Start my first check", href: "#/new" } },
  ],
  check: [
    { target: "verdict", icon: "gavel", title: "The verdict", body: "One plain sentence on what happened, plus how sure FinSync is about it." },
    { target: "amounts", icon: "currency_rupee", title: "The money", body: "What was expected, what actually reached your bank, and what's still due." },
    { target: "tabs", icon: "tab", title: "Go deeper", body: "Records shows every file and bank entry used. Your answer is where you confirm what happened. Follow-ups drafts reminders and accounting entries. History keeps a tamper-proof log." },
    { target: "ask", icon: "auto_awesome", title: "Ask questions", body: "Ask anything in plain English — answers come only from your own records." },
  ],
};

const tour = { name: null, steps: [], i: 0, layer: null, onResize: null };

function tourKey(name) { return `verity.tour.${name}.${state.user?.id || "anon"}`; }
function tourSeen(name) { try { return localStorage.getItem(tourKey(name)) === "1"; } catch { return false; } }
function markTourSeen(name) { try { localStorage.setItem(tourKey(name), "1"); } catch { /* storage unavailable */ } }

function maybeStartTours(page, sub) {
  if (tour.name) return;
  if (!page && !tourSeen("main")) setTimeout(() => startTour("main"), 400);
  else if (page === "checks" && sub && !tourSeen("check") && tourSeen("main")) setTimeout(() => startTour("check"), 500);
}

function visibleTarget(name) {
  return $$(`[data-tour="${name}"]`).find((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  });
}

function startTour(name, force = false) {
  if (!force && tourSeen(name)) return;
  stopTour();
  tour.name = name;
  tour.steps = TOURS[name].filter((s) => !s.target || visibleTarget(s.target));
  tour.i = 0;
  const layer = document.createElement("div");
  layer.className = "tour-layer";
  layer.innerHTML = `<div class="tour-blocker"></div><div class="tour-spot center"></div><div class="tour-card" role="dialog" aria-modal="true" aria-live="polite"></div>`;
  document.body.appendChild(layer);
  tour.layer = layer;
  tour.onResize = debounce(() => drawTourStep(), 80);
  window.addEventListener("resize", tour.onResize);
  layer.addEventListener("click", (e) => {
    const act = e.target.closest("[data-tour-act]")?.dataset.tourAct;
    if (act === "next") nextTourStep();
    else if (act === "back") { tour.i = Math.max(0, tour.i - 1); drawTourStep(); }
    else if (act === "skip") endTour();
    else if (act === "cta") { const href = e.target.closest("[data-href]")?.dataset.href; endTour(); if (href) location.hash = href; }
  });
  document.addEventListener("keydown", tourKeys);
  drawTourStep();
}

function tourKeys(e) {
  if (!tour.layer) return;
  if (e.key === "Escape") endTour();
  else if (e.key === "ArrowRight") nextTourStep();
  else if (e.key === "ArrowLeft") { tour.i = Math.max(0, tour.i - 1); drawTourStep(); }
}

function nextTourStep() {
  if (tour.i >= tour.steps.length - 1) endTour();
  else { tour.i++; drawTourStep(); }
}

function drawTourStep() {
  if (!tour.layer) return;
  const step = tour.steps[tour.i];
  const spot = $(".tour-spot", tour.layer);
  const card = $(".tour-card", tour.layer);
  const last = tour.i === tour.steps.length - 1;
  card.innerHTML = `
    <span class="tour-count">${tour.i + 1} of ${tour.steps.length}</span>
    <h3>${esc(step.title)}</h3>
    <p>${esc(step.body)}</p>
    <div class="foot">
      <div class="tour-dots" aria-hidden="true">${tour.steps.map((_, j) => `<i class="${j <= tour.i ? "on" : ""}"></i>`).join("")}</div>
      <div class="btns">
        ${last && step.cta ? `<button class="btn btn-ghost btn-sm" data-tour-act="skip">Later</button><button class="btn btn-primary btn-sm" data-tour-act="cta" data-href="${esc(step.cta.href)}">${esc(step.cta.label)}</button>` : `
          ${tour.i === 0 ? `<button class="btn btn-ghost btn-sm" data-tour-act="skip">Skip</button>` : `<button class="btn btn-ghost btn-sm" data-tour-act="back">Back</button>`}
          <button class="btn btn-primary btn-sm" data-tour-act="next">${last ? "Done" : tour.i === 0 && tour.name === "main" ? "Show me" : "Next"}</button>`}
      </div>
    </div>`;

  const target = step.target ? visibleTarget(step.target) : null;
  const vw = window.innerWidth, vh = window.innerHeight;
  const cw = Math.min(360, vw - 32);

  if (!target) {
    spot.classList.add("center");
    card.style.left = `${(vw - cw) / 2}px`;
    card.style.top = `${Math.max(16, vh / 2 - card.offsetHeight / 2)}px`;
  } else {
    target.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const r = target.getBoundingClientRect();
    const pad = 6;
    spot.classList.remove("center");
    Object.assign(spot.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px` });
    const ch = card.offsetHeight;
    let top, left;
    if (r.right + 16 + cw < vw && r.height < vh / 2 && vw >= 960) {
      left = r.right + 18; top = Math.min(Math.max(16, r.top + r.height / 2 - ch / 2), vh - ch - 16);
    } else if (r.bottom + 14 + ch < vh) {
      top = r.bottom + 14; left = Math.min(Math.max(16, r.left + r.width / 2 - cw / 2), vw - cw - 16);
    } else {
      top = Math.max(16, r.top - ch - 14); left = Math.min(Math.max(16, r.left + r.width / 2 - cw / 2), vw - cw - 16);
    }
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }
  $("[data-tour-act=next], [data-tour-act=cta]", card)?.focus({ preventScroll: true });
}

function endTour() {
  if (tour.name) markTourSeen(tour.name);
  stopTour();
}

function stopTour() {
  tour.layer?.remove();
  if (tour.onResize) window.removeEventListener("resize", tour.onResize);
  document.removeEventListener("keydown", tourKeys);
  tour.layer = null; tour.name = null; tour.onResize = null;
}

/* ---------------------------------------------------------
   Boot
   --------------------------------------------------------- */
window.addEventListener("hashchange", () => { stopTour(); render().then(() => $("#view")?.focus({ preventScroll: true })); window.scrollTo(0, 0); });

(async function boot() {
  applyTheme(getThemePref());
  await initAuth();
  if (state.welcomeToast) { setTimeout(() => toast(state.welcomeToast, "success"), 300); state.welcomeToast = null; }
  render();
})();
