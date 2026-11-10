/* Local stand-in for ascii-magic.com's lib/kit.js, so the pieces render offline.
 * To render with the real kit instead: node tools/ascii/fetch.mjs (or see tools/ascii/README). */
export const TAU = Math.PI * 2;
export const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const KEYS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+,-./:;<=>?@[]^_{|}~".split("");

export function rng(seed = 1) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const hash = (x, y, s) => { let h = Math.imul(x * 374761393 + y * 668265263 + s * 2147483647, 1274126177); h ^= h >>> 15; h = Math.imul(h, 2246822519); h ^= h >>> 13; return (h >>> 0) / 4294967296; };
const sm = (t) => t * t * (3 - 2 * t);
export function noise2(x, y, seed = 0) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = sm(x - xi), yf = sm(y - yi);
  const a = hash(xi, yi, seed), b = hash(xi + 1, yi, seed), c = hash(xi, yi + 1, seed), d = hash(xi + 1, yi + 1, seed);
  return lerp(lerp(a, b, xf), lerp(c, d, xf), yf);
}
export function fbm(x, y, oct = 4, seed = 0) {
  let v = 0, amp = 0.5, tot = 0, f = 1;
  for (let i = 0; i < oct; i++) { v += amp * noise2(x * f, y * f, seed + i * 17); tot += amp; amp *= 0.5; f *= 2; }
  return v / tot;
}
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const toHex = (c) => "#" + c.map((v) => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, "0")).join("");
export function gradient(stops, n) {
  const cs = stops.map(hex), out = [];
  for (let i = 0; i < n; i++) {
    const t = (i / Math.max(1, n - 1)) * (cs.length - 1), k = Math.min(cs.length - 2, Math.floor(t)), f = t - k;
    out.push(toHex(cs[k].map((v, j) => lerp(v, cs[k + 1][j], f))));
  }
  return out;
}
export const palette = (all) => Object.fromEntries(all.map((c, i) => [KEYS[i], c]));

export class Grid {
  constructor(cols, rows) { this.cols = cols; this.rows = rows; this.ch = new Array(cols * rows).fill(" "); this.key = new Array(cols * rows).fill(" "); }
  clear() { this.ch.fill(" "); this.key.fill(" "); }
  set(x, y, ch, key) { x = Math.floor(x); y = Math.floor(y); if (x < 0 || y < 0 || x >= this.cols || y >= this.rows) return; const i = x + y * this.cols; this.ch[i] = ch; this.key[i] = key === undefined ? " " : key; }
  get(x, y) { x = Math.floor(x); y = Math.floor(y); if (x < 0 || y < 0 || x >= this.cols || y >= this.rows) return " "; return this.ch[x + y * this.cols]; }
  text(x, y, s, key) { for (let i = 0; i < s.length; i++) this.set(x + i, y, s[i], key); }
  frame() {
    const t = [], c = [];
    for (let y = 0; y < this.rows; y++) { t.push(this.ch.slice(y * this.cols, (y + 1) * this.cols).join("")); c.push(this.key.slice(y * this.cols, (y + 1) * this.cols).join("")); }
    return { text: t.join("\n"), color: c.join("\n") };
  }
}
