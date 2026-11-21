# 光市の品目データの作り方（記録）

光市「ごみ分別事典（平成29年7月）」`01ziten.pdf` は文字が画像（図形）なので、
Windows 標準の日本語 OCR で読み取り、読み違いを手で直して `index.html` の `ITEMS_HIKARI` にした。

1. PDF の 8〜24ページ目（50音順分別早見表）と 25ページ目（雑がみ事典）を 400dpi の画像にする（pymupdf）
2. `ocr.ps1` で OCR（Windows の OCR エンジン・日本語）。1文字ずつの位置が TSV で出る
3. `parse_hikari.py`：表の行を組み立てる。品目ごとの背景色（白・水色）で品目の区切りを見分ける
4. `clean_hikari.py`：OCR が品名を読めなかった行・区分の文字が小さくて読めなかった行を、画像を見て補う
5. `parse_zatsu.py`：雑がみ事典の行を読む
6. `final_hikari.py`：濁点の抜けなどの読み違いを直し、読み（pykakasi）を付けて `items_hikari.json` を作る

スクリプトの中のフォルダの場所は、作ったときの作業フォルダのまま。
収集日（カレンダー）は `../calendar.py` で作る（毎年 tools/update_year.py から使う）。できた品目は `gomiappV3.0/data/35_yamaguchi/35210_hikari/items.js`（1行に1品目）。
