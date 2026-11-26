"""状況一覧（管理アプリ）を、ボタンで更新できるようにして開く。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/admin.py          ← ブラウザで http://127.0.0.1:8766/ が開く
  python gomiappV3.1/tools/admin.py --no-open ← ブラウザを開かない
止めるときは、この画面で Ctrl+C。

状況一覧の「自治体ごと」の表に、ボタンが出る（「次の年度」は、今の年度の次。例：今が令和8年度なら令和9年度）：
  元データの列「最新をチェック」 … 市のサイトに次の年度のカレンダーが出ているか（download_sources.py --list。保存しない）
                                   オープンデータを使う自治体は、カタログの更新日も見る（update_opendata.py --check）
  道具の列「令和○年度を試す」   … 次の年度のカレンダーを取ってきて、読み取れるか試す
                                   （download_sources.py → update_year.py --preview。アプリのデータは変えない）
  いちばん上「令和○年度に切り替える（全部）」… 3月1日から押せる。全部の自治体を次の年度にする
                                   （download_sources.py → update_year.py → check_muni.py → status.py）
  いちばん上「状況一覧を作り直す」 … status.py
アプリには1年度分の収集日しか入らないので、切り替えは年度の始まり（4月）の少し前にする。

このパソコンの中だけで動く（127.0.0.1）。動かせるのは上の道具だけで、ほかのサイトからは動かせない。
作り直したら、アプリをブラウザで確かめてから、GitHub Desktop で Commit → Push origin。
"""
import datetime as dt
import json
import re
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
NL = "\n"


def next_year(today=None):
    """次の年度（4月始まり）"""
    t = today or dt.date.today()
    return (t.year if t.month >= 4 else t.year - 1) + 1


def can_switch(today=None):
    """全部の自治体を次の年度に切り替えてよいか（3月1日から）"""
    return (today or dt.date.today()) >= dt.date(next_year(today), 3, 1)


def set_published(code, on):
    """data/municipalities.js の自治体に "hidden": true を付ける（公開しない）か外す（公開する）。
    公開しない自治体は、アプリの市町村の一覧・今いる場所から探すに出ない（データは残る）"""
    path = M.DATA / "municipalities.js"
    text = path.read_text(encoding="utf-8")
    m = re.search(r"/\*MUNIS-START\*/(.*)/\*MUNIS-END\*/", text, re.S)
    reg = json.loads(m.group(1))
    hit = next((x for x in reg["munis"] if x["code"] == code), None)
    if not hit:
        raise ValueError("自治体コードがちがいます")
    if on:
        hit.pop("hidden", None)
    else:
        hit["hidden"] = True
    body = json.dumps(reg, ensure_ascii=False, indent=1)
    path.write_text(text[:m.start(1)] + body + text[m.end(1):], encoding="utf-8", newline=NL)
    return (f"{hit['name']}（{code}）を{'公開する' if on else '公開しない'}にしました（data/municipalities.js）。{NL}"
            "アプリに反映するには、GitHub Desktop で Commit → Push origin。")


def steps(tool, code):
    """ボタン → 順に動かすコマンド（決まったものだけ）。(説明, コマンド, 失敗しても続けるか)"""
    py = [sys.executable, "-X", "utf8"]
    t = lambda f, *a: py + [str(TOOLS / f)] + [str(x) for x in a]  # noqa: E731
    ny = next_year()
    if tool == "status":
        return [("状況一覧を作り直す", t("status.py"), False)]
    if tool == "switch":
        if not can_switch():
            raise ValueError(f"切り替えは {dt.date(ny, 3, 1):%Y年%m月%d日} から押せます（アプリには1年度分しか入らないため）")
        return [("市のサイトから取ってくる（全部）", t("download_sources.py", ny), False),
                (f"{M.nendo(ny)}のデータを作る（全部）", t("update_year.py", ny), False),
                ("自動チェック（全部）", t("check_muni.py"), True),
                ("状況一覧を作り直す", t("status.py"), False)]
    ms = {m.code: m for m in M.munis()}
    if code not in ms:
        raise ValueError("自治体コードがちがいます")
    if tool == "latest":
        out = [(f"市のサイトに{M.nendo(ny)}のカレンダーが出ているか見る", t("download_sources.py", ny, code, "--list"), True)]
        if ms[code].module("opendata"):
            out.append(("オープンデータのカタログの更新日を見る", t("update_opendata.py", code, "--check"), True))
        return out
    if tool == "trynext":
        # 見つからないものがあっても続ける（足りないかどうかは、次の「試す」が調べる）
        return [(f"{M.nendo(ny)}のカレンダーを取ってくる", t("download_sources.py", ny, code), True),
                ("読み取れるか試す（アプリのデータは変えない）", t("update_year.py", ny, code, "--preview"), False)]
    raise ValueError("知らないボタンです")


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
                subprocess.run(steps("status", None)[0][1], cwd=ROOT)
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/ping":
            return self.send(200, "ok")
        self.send(404, "ありません")

    def do_POST(self):
        if not self.same_site() or self.path != "/api/run" or self.headers.get("Content-Type") != "application/json":
            return self.send(403, "だめです")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if req.get("tool") == "publish":
                with LOCK:
                    return self.send(200, set_published(str(req.get("code")), bool(req.get("on"))))
            plan = steps(req.get("tool"), req.get("code"))
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
            ok_all = True
            for i, (title, cmd, soft) in enumerate(plan, 1):
                shown = "python gomiappV3.1/tools/" + " ".join(Path(c).name if c.endswith(".py") else c for c in cmd[3:])
                print("動かします:", shown)
                self.wfile.write(f"{'' if i == 1 else NL}■ {i}/{len(plan)} {title}{NL}$ {shown}{NL}".encode("utf-8"))
                self.wfile.flush()
                p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                for line in p.stdout:
                    self.wfile.write(line)
                    self.wfile.flush()
                p.wait()
                if p.returncode != 0:
                    ok_all = False
                    if not soft:
                        self.wfile.write(f"{NL}［おわり：ここで止まりました。上の文を見てください］{NL}".encode("utf-8"))
                        break
            else:
                tool = req.get("tool")
                end = ("うまくいきました" if ok_all else
                       "まだ出ていないものがあります（上の「見つからなかったもの」を見てください）" if tool == "latest" else
                       "気をつけることがあります。上の文を見てください")
                self.wfile.write(f"{NL}［おわり：{end}］{NL}".encode("utf-8"))
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
