"""状況一覧（管理アプリ）を、ボタンで更新できるようにして開く。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/admin.py          ← ブラウザで http://127.0.0.1:8766/ が開く
  python gomiappV3.1/tools/admin.py --no-open ← ブラウザを開かない
止めるときは、この画面で Ctrl+C。

状況一覧の「自治体ごとのくわしく」に、自治体ごとの「更新」ボタンが出る：
  市のサイトを見る（download_sources.py <年度> <コード> --list） … 新しい年度のカレンダーが出ているか（保存しない）
  取ってくる      （download_sources.py <年度> <コード>）        … 元データ/ に保存
  作り直す        （update_year.py <年度> <コード>）              … data/ と geo/ を作り直す
  オープンデータ  （update_opendata.py <コード>）                 … 最新を取ってきて作り直す（オープンデータを使う自治体だけ）
  自動チェック    （check_muni.py <コード>）
上の「状況一覧を作り直す」は status.py。

このパソコンの中だけで動く（127.0.0.1）。動かせるのは上の道具だけで、ほかのサイトからは動かせない。
作り直したら、アプリをブラウザで確かめてから、GitHub Desktop で Commit → Push origin。
"""
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / "lib"))
import munis as M  # noqa: E402

HOST, PORT = "127.0.0.1", 8766
ROOT = TOOLS.parents[1]          # gomi フォルダ（道具はここで動かす）
PAGE = M.SOURCES / "状況一覧.html"
LOCK = threading.Lock()          # 1つずつ動かす


def command(tool, code, year):
    """ボタン → 動かすコマンド。決まったものだけ"""
    py = [sys.executable, "-X", "utf8"]
    t = lambda f: str(TOOLS / f)  # noqa: E731
    if tool == "status":
        return py + [t("status.py")]
    codes = {m.code for m in M.munis()}
    if code not in codes:
        raise ValueError("自治体コードがちがいます")
    if not (isinstance(year, int) and 2020 <= year <= 2100):
        raise ValueError("年度がちがいます")
    return {
        "list": py + [t("download_sources.py"), str(year), code, "--list"],
        "download": py + [t("download_sources.py"), str(year), code],
        "update": py + [t("update_year.py"), str(year), code],
        "opendata": py + [t("update_opendata.py"), code],
        "check": py + [t("check_muni.py"), code],
    }[tool]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def same_site(self):
        ok = {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}
        host_ok = self.headers.get("Host") in {f"{HOST}:{PORT}", f"localhost:{PORT}"}
        origin = self.headers.get("Origin")
        return host_ok and (origin is None or origin in ok)

    def send(self, code, body, ctype="text/plain; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if not self.same_site():
            return self.send(403, "だめです")
        if self.path in ("/", "/index.html"):
            if not PAGE.exists():
                subprocess.run(command("status", None, None), cwd=ROOT)
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/ping":
            return self.send(200, "ok")
        self.send(404, "ありません")

    def do_POST(self):
        if not self.same_site() or self.path != "/api/run" or self.headers.get("Content-Type") != "application/json":
            return self.send(403, "だめです")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            cmd = command(req.get("tool"), req.get("code"), req.get("year"))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            return self.send(400, f"動かせません：{e}")
        if not LOCK.acquire(blocking=False):
            return self.send(409, "ほかの更新が動いています。終わってからもう一度押してください。")
        try:
            # 出てきた文字を、そのまま少しずつ送る
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            shown = "python gomiappV3.1/tools/" + " ".join(Path(c).name if c.endswith(".py") else c for c in cmd[3:])
            print("動かします:", shown)
            self.wfile.write(f"$ {shown}\n".encode("utf-8"))
            p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in p.stdout:
                self.wfile.write(line)
                self.wfile.flush()
            p.wait()
            if p.returncode == 0:
                end = "うまくいきました"
            elif req.get("tool") in ("list", "download"):
                end = "まだ見つからないものがあります（市がまだ出していないか、市のページが変わっています）"
            elif req.get("tool") == "check":
                end = "「直す」があります。上の文を見てください"
            else:
                end = f"エラー（{p.returncode}）。上の文を見てください"
            self.wfile.write(f"\n［おわり：{end}］\n".encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            LOCK.release()


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"管理アプリ：{url}  （止めるときは Ctrl+C）")
    if "--no-open" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("止めました")


if __name__ == "__main__":
    main()
