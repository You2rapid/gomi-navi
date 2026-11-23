// アプリの中身（../gomiappV3.1）を www/ に写す。ストアのアプリには www/ の中身が入る。
// 写さないもの：tools/（データを作る道具）、sw.js（オフライン用のしくみ。ストアのアプリでは使わない）
//   zip/（郵便番号・全国で約9MB）は、アプリに入っている県（data/municipalities.js）の分と index.json だけ写す。
//   ほかの県の郵便番号は、入れたときに公開ページから読む（「このアプリに入っていません」と出すため）
// 使い方：npm run copy（npm run sync・android・ios でも先に動く）
import { cpSync, rmSync, existsSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(dirname(fileURLToPath(import.meta.url)));
const SRC = join(here, "..", "gomiappV3.1");
const DEST = join(here, "www");
const SKIP = ["tools", "sw.js"];

if (!existsSync(join(SRC, "index.html"))) {
  console.error("アプリの中身が見つかりません：" + SRC);
  process.exit(1);
}
const prefs = new Set([...readFileSync(join(SRC, "data", "municipalities.js"), "utf8").matchAll(/"pref":\s*"(\d\d)"/g)].map((m) => m[1]));
rmSync(DEST, { recursive: true, force: true });
cpSync(SRC, DEST, {
  recursive: true,
  filter: (p) => {
    const parts = relative(SRC, p).split(sep);
    if (SKIP.includes(parts[0])) return false;
    if (parts[0] === "zip" && parts[1] && parts[1] !== "index.json") return prefs.has(parts[1].slice(0, 2));
    return true;
  },
});
console.log(`写しました：${SRC} → ${DEST}`);
