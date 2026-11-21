"""市のサイトからページやファイルを取ってくる（download_sources.py と各自治体の calendar.py の download で使う）"""
import html
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin

UA = {"User-Agent": "Mozilla/5.0 (gomi-calendar updater)"}


def get(url):
    time.sleep(0.5)   # 市のサーバーに負担をかけないよう、少し間をあける
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.read()
    except urllib.error.URLError as e:
        # Python と暗号のやり方が合わないサーバー（山口県オープンデータカタログなど）は、パソコンの curl で取る
        if "SSL" not in str(e.reason) or not shutil.which("curl"):
            raise
        return subprocess.run(["curl", "-sSfL", "--max-time", "60", "-A", UA["User-Agent"], url], capture_output=True, check=True).stdout


def text(raw):
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def links(page_html, base):
    """ページの中のリンク（URL, リンクの文字）の一覧"""
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        label = re.sub(r"<[^>]+>|\s+", " ", html.unescape(label)).strip()
        out.append((urljoin(base, html.unescape(href)), label))
    return out


class Plan:
    """ダウンロードする予定（URL → 保存先）と、見つからなかったもの"""
    def __init__(self):
        self.todo, self.problems = [], []

    def add(self, url, path, raw=None):
        self.todo.append((url, path, raw))

    def problem(self, msg):
        self.problems.append(msg)
