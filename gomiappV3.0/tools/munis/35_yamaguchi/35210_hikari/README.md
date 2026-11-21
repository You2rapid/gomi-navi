# 山口県 光市（35210）

- アプリのデータ：`gomiappV3.0/data/35_yamaguchi/35210_hikari/`
- 元データ：`元データ/35_山口県/35210_光市/`
- 問い合わせ：環境事業課 ごみ・リサイクル対策係 0833-72-1471

## 収集日（毎年）

ダウンロード元：https://www.city.hikari.lg.jp/kurashi_tetsuzuki/gomi/bunbetu/8851.html の7地区のPDF
（令和8年度は `081gomicalendermurozumi.pdf`〜`087gomicalenderyamato.pdf`。先頭2けたが令和の年）を、
`murozumi.pdf`・`mitsui.pdf`・`shimata.pdf`・`asaekita.pdf`・`asaeminami.pdf`・`mishima.pdf`・`yamato.pdf` の名前で置く。

注意：
- **大和地区だけ、出す時刻が朝7時30分まで**（`calendar.py` の `CUT`）。変わっていないか確かめる。
- 地区の名前と住所は `calendar.py` の `AREAS`（カレンダーの左上に書いてある住所）。地区の分け方が変わったら直す（`geo.py` の `HIKARI_TOWNS` も）。
- 収集の札は色と文字の形で、日付は数字の形で読み取る。どの月も全部の日がそろっているかを確かめ、読めないと止まる。

## 品目（冊子が改定されたとき）

「ごみ分別事典（平成29年7月）」（`分別の冊子/`）は文字が図形のPDFなので、Windows の OCR で読み取り、読み違いを手で直した。
手順の記録は `items/README.md`。

## 今いる場所から探す

`geo.py`：e-Stat の町名 → 地区（カレンダーの住所から）。「一部」と書かれた町（大字室積村・大字島田など）は2つの地区を候補に出す。
