// Run a piece and dump its frames as JSON: node render.mjs <slug> <out.json> [t0] [t1] [fps] [tscale]
// Also: node render.mjs <slug> <out.json> still <t>    -> one frame at time t
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const [slug, out, a, b, c, d] = process.argv.slice(2);
const mod = await import(pathToFileURL(resolve(here, "pieces", `${slug}.js`)).href);
const draw = mod.default();
const frames = [];
if (a === "still") {
  frames.push(draw(parseFloat(b)));
} else {
  const t0 = parseFloat(a ?? 0), t1 = parseFloat(b ?? 4), fps = parseFloat(c ?? mod.meta.fps), k = parseFloat(d ?? 1);
  const n = Math.round((t1 - t0) * fps);
  for (let i = 0; i < n; i++) frames.push(draw(t0 + (i / fps) * k));
}
const { cols, rows, palette, cell, look } = mod.meta;
writeFileSync(out, JSON.stringify({ slug, cols, rows, palette, cell, look, frames }));
console.log(`${slug}: ${frames.length} frame(s) -> ${out}`);
