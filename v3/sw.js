// オフライン対応用 Service Worker
// ・ネットにつながるときは最新版を取得してキャッシュを更新（ネットワーク優先）
// ・つながらないときはキャッシュから表示
// ファイル構成を変えたときは VERSION を上げてください。
// 自治体ごとのデータ（data/<県>/<自治体>/）と地図（geo/）は、一度開いたものが下のしくみで保存される。
// 同じサイトにある旧版（gomi-v1・gomi2-）のキャッシュを消さないよう、名前は "gomi3-" で始める。
const PREFIX = "gomi3-";
const VERSION = PREFIX + "v4";
const FILES = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./data/municipalities.js",
  "./data/holidays.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-192.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith(PREFIX) && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  // カメラ判定用の AI データ（ai/ 以下・約15MB）は中身が変わらないので、一度保存したらキャッシュを優先する
  if (new URL(req.url).pathname.includes("/ai/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
        return res;
      }))
    );
    return;
  }
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req, { ignoreSearch: true }).then(
          (hit) => hit || (req.mode === "navigate" ? caches.match("./index.html") : Response.error())
        )
      )
  );
});
