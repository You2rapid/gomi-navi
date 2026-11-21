// アプリの中身（../gomiappV3.1）を www/ に写す。ストアのアプリには www/ の中身が入る。
// 写さないもの：tools/（データを作る道具）、sw.js（オフライン用のしくみ。ストアのアプリでは使わない）
// 使い方：npm run copy（npm run sync・android・ios でも先に動く）
import { cpSync, rmSync, existsSync } from "node:fs";
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
rmSync(DEST, { recursive: true, force: true });
cpSync(SRC, DEST, {
  recursive: true,
  filter: (p) => {
    const top = relative(SRC, p).split(sep)[0];
    return !SKIP.includes(top);
  },
});
console.log(`写しました：${SRC} → ${DEST}`);
