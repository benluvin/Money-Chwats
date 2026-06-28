import * as esbuild from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const watch = process.argv.includes("--watch");
const root = dirname(fileURLToPath(import.meta.url));
const outdir = join(root, "dist");

await rm(outdir, { recursive: true, force: true });
await mkdir(outdir, { recursive: true });

const entryPoints = [
  "src/background.ts",
  "src/content-script.ts",
  "src/popup.ts",
];

const opts = {
  entryPoints,
  bundle: true,
  format: "esm",
  target: "chrome120",
  outdir,
  sourcemap: true,
  logLevel: "info",
};

// Copia estáticos (manifest, popup html/css, icons)
async function copyStatics() {
  await cp(join(root, "manifest.json"), join(outdir, "manifest.json"));
  await cp(join(root, "src", "popup.html"), join(outdir, "popup.html"));
  await cp(join(root, "src", "popup.css"), join(outdir, "popup.css"));
  if (existsSync(join(root, "icons"))) {
    await cp(join(root, "icons"), join(outdir, "icons"), { recursive: true });
  }
}

if (watch) {
  const ctx = await esbuild.context(opts);
  await ctx.watch();
  await copyStatics();
  console.log("watching for changes...");
} else {
  await esbuild.build(opts);
  await copyStatics();
  console.log("build OK →", outdir);
}
