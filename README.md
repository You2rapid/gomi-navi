# ごみ出しカレンダー（非公式）

ごみの収集日カレンダーと分別検索のアプリです（いまは山口県の周南市・下松市・光市。3.1 では京都府の京都市も）。
スマホのホーム画面に追加して、アプリのように使えます（PWA・オフライン対応）。

- アプリ：https://you2rapid.github.io/gomi-navi/gomiappV3.0/
- このページのいちばん上（https://you2rapid.github.io/gomi-navi/）や、前の場所（`/v3/`）を開くと、自動でアプリに移ります。

> 非公式ツールです。最新の情報や収集日は、お住まいの地域のごみ収集カレンダーや市ホームページで確認してください。

## フォルダ

| 場所 | 内容 |
| --- | --- |
| `gomiappV3.0/` | アプリ本体（ごみ出しカレンダー 3.0）。データと作る道具も入っている |
| `gomiappV3.1/` | 次の版（3.1）。3.0 に通知を足したもの。https://you2rapid.github.io/gomi-navi/gomiappV3.1/ <br>・カレンダーの日にちを長押し →「🔔 この日を知らせる」で、その日だけ1回知らせる（時刻はスライドバーで決める）<br>・開いたときに「あしたは○○の日です」を出す<br>・地区をえらぶ画面で、郵便番号（7けた）から地区の候補を出す（zip/：日本郵便のデータ、tools/build_zip.py で作る） |
| `gomiapp-store/` | ストア版（iPhone・Android のアプリ）。gomiappV3.1 を Capacitor で包んだもの。作り方は gomiapp-store/README.md |
| `gomiappV3.0/tools/README.md` | データの置き場所、毎年4月の更新、自治体の増やし方、状況一覧 |
| `index.html`・`v3/index.html` | 前の場所から新しい場所へ案内するページ |
| `元データ/` | 市のPDFなどの元の資料（このパソコンだけ。GitHub には上げない） |

初版（分別検索）と v2（周南市の収集日カレンダー）は公開をやめました。中身は Git の履歴に残っています。

## スマホへの追加

- **iPhone**：Safari で上のアプリのURLを開き、共有ボタン →「ホーム画面に追加」
- **Android**：Chrome で上のアプリのURLを開き、メニュー（︙）→「ホーム画面に追加」または「アプリをインストール」

一度開けば、電波がなくても使えます。

## 更新のしかた

ファイルを直したら、GitHub Desktop で Commit → **Push origin**。
次にスマホでアプリを開いたとき（ネット接続時）に新しい版へ切り替わります。

## 公開のしかた（GitHub Pages）

リポジトリの **Settings → Pages** で、Source を「Deploy from a branch」、Branch を「main」「/(root)」にしています。
