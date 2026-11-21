# 山口県 下松市（35207）

- アプリのデータ：`gomiappV3.1/data/35_yamaguchi/35207_kudamatsu/`
- 元データ：`元データ/35_山口県/35207_下松市/`
- 問い合わせ：環境推進課 廃棄物対策係 0833-45-1829

## 収集日（毎年）

ダウンロード元：https://www.city.kudamatsu.lg.jp/kankyou/seikatsu/kankyou/kannrikakari/gomikarenda.html の「A4・月ごと」の版
（令和8年度は `r8nishia4.pdf`・`r8higashia4.pdf`）を、`nishi.pdf`（西地区）・`higashi.pdf`（東地区）の名前で置く。

注意：
- 地区の説明（どこが西地区・東地区か）は `calendar.py` の `make_calendar` の中に書いてある。分け方が変わったら直す。
- マスの位置（`COLS`・`ROW_TOP`・`ROW_H`）と、区分を見分ける図形の形（`SIG`）はPDFに合わせてある。変わると読み取れない区分が「?」で出る。

## 品目

「家庭ごみ分別事典（令和5年5月）」（`分別の冊子/`）に例として載っている品目を、手で `items.js` に入れている（155件）。

## 今いる場所から探す

`geo.py`：市のサイトの地図（`地図/西地区東地区の地図.jpg`）から読み取った、西地区・東地区の境目の線 `KUDA_LINE`。

## 商用利用

`license.json` に、使っている資料ごとの利用条件と、許可の問い合わせ先を書いている（状況一覧の「商用利用」の列）。
