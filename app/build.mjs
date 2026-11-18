// build.mjs - empacota o app React em app/dist (que o backend serve).
//   npm install      (so na primeira vez)
//   npm run build    gera dist/
//   npm run dev      reconstroi sozinho a cada alteracao
import * as esbuild from "esbuild";
import { cpSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
cpSync("public", "dist", { recursive: true });

const opcoes = {
  entryPoints: ["src/main.jsx"],
  bundle: true,
  minify: true,
  sourcemap: false,
  outfile: "dist/app.js",
  loader: { ".css": "css" },
  jsx: "automatic",
  define: { "process.env.NODE_ENV": '"production"' },
  target: ["es2020"],
};

if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context(opcoes);
  await ctx.watch();
  console.log("observando src/ ...");
} else {
  await esbuild.build(opcoes);
  console.log("pronto: app/dist");
}
