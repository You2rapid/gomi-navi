"""オープンデータ（CKAN のカタログ。例：山口県オープンデータカタログサイト）からファイルを取ってくる部品。

  info(dataset_url, web)                      … データセットの情報（題名・ライセンス・更新日・ファイルの一覧）
  fetch(dataset_url, dest, pick, web)         … pick に合うファイルを1つ dest に保存し、横に <名前>.meta.json（どこから・いつ更新）を書く
  meta(path)                                  … 保存したファイルの .meta.json を読む（なければ None）

dataset_url はデータセットのページの URL（https://<カタログ>/ckan/dataset/<ID>）。
カタログの API（https://<カタログ>/ckan/api/3/action/package_show）で情報を取る。
"""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse


def _api(dataset_url):
    u = urlparse(dataset_url)
    root, _, ds = u.path.partition("/dataset/")
    return f"{u.scheme}://{u.netloc}{root}/api/3/action/package_show?id={ds.strip('/')}"


def info(dataset_url, web):
    d = json.loads(web.get(_api(dataset_url)).decode("utf-8"))
    if not d.get("success"):
        raise RuntimeError(f"カタログから情報が取れません：{dataset_url}")
    r = d["result"]
    return {
        "title": r.get("title", ""),
        "license": r.get("license_title") or r.get("license_id", ""),
        "modified": (r.get("metadata_modified") or "")[:10],
        "resources": [{"name": x.get("name", ""), "format": (x.get("format") or "").upper(), "url": x.get("url", ""),
                       "modified": (x.get("last_modified") or x.get("created") or "")[:10]} for x in r.get("resources", [])],
    }


def fetch(dataset_url, dest, pick, web):
    """pick(resource) が True になる最初のファイルを dest に保存する。見つからなければ None"""
    i = info(dataset_url, web)
    res = next((x for x in i["resources"] if pick(x)), None)
    if not res:
        return None
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(web.get(res["url"]))
    m = {"dataset": dataset_url, "title": i["title"], "license": i["license"], "resource": res["name"],
         "url": res["url"], "modified": res["modified"] or i["modified"], "fetched": dt.date.today().isoformat()}
    dest.with_name(dest.name + ".meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def meta(path):
    f = Path(path).with_name(Path(path).name + ".meta.json")
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
