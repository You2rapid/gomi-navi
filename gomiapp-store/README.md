# ごみ出しカレンダー ストア版（iPhone・Android のアプリ）

`../gomiappV3.1/`（ブラウザ版）をそのまま、[Capacitor](https://capacitorjs.com/) で iPhone・Android のアプリの「箱」に入れたものです。
アプリの中身を直すときは `gomiappV3.1/` を直します（このフォルダの `www/` は写しなので、直さない）。

## ブラウザ版とのちがい（index.html の中で `NATIVE` で切り替えている）

| | ブラウザ版 | ストア版 |
| --- | --- | --- |
| 通知 | 収集日を通知つきでスマホのカレンダーに入れるファイル（.ics）を作る | **スマホの中で通知を予約する**（ローカル通知）。近い順に60件を予約し、アプリを開くたびに予約し直す |
| データ | 同じ場所から読む（オフラインは Service Worker） | まず公開ページ（`REMOTE`）から読み、スマホに保存。電波がなければ保存したもの、なければアプリに入っているもの。**毎年4月の更新は、公開ページを直すだけで届く（審査なし）** |
| アイコンの数字の印 | 対応するスマホだけ | なし |

## フォルダ

| 場所 | 中身 |
| --- | --- |
| `package.json` | 使う部品（Capacitor・ローカル通知）と、よく使うコマンド |
| `capacitor.config.json` | アプリの ID（`appId`）・名前・通知のアイコン |
| `scripts/copy-web.mjs` | `../gomiappV3.1` を `www/` に写す（`tools/` と `sw.js` は写さない） |
| `assets/` | アイコンの元の絵（`python gomiappV3.1/tools/make_icons.py` で作る） |
| `android/` | Android のアプリ（Android Studio で開く） |
| `ios/` | iPhone のアプリ（Mac で `npx cap add ios` すると作られる。まだない） |

`node_modules/`・`www/`・署名の鍵は GitHub に上げません（`.gitignore`）。

## はじめに（1回だけ）

1. このフォルダで `npm install`
2. **Android**：[Android Studio](https://developer.android.com/studio) を入れる（Java もいっしょに入る）
3. **iPhone**：Mac に Xcode を入れ、このフォルダで `npx cap add ios`（下の「iPhone 版」）

## Android で試す

```
npm run android
```

`gomiappV3.1` を写して Android Studio が開きます。

- **スマホで試す**：Android のスマホの「設定」→「デバイス情報」→「ビルド番号」を7回タップして「開発者向けオプション」を出し、「USB デバッグ」をオンにして、USB でパソコンにつなぎます。Android Studio の上の ▶（Run）を押すとスマホに入ります。
- **スマホがないとき**：Android Studio の「Device Manager」で、パソコンの中のスマホ（エミュレーター）を作って ▶ を押します。
- 通知を試すには、地区をえらんでカレンダーの日にちを長押し →「🔔 前の日の夜7時に知らせる」。「通知の設定」で「当日の朝」なども選べます。

## iPhone 版（Mac で）

1. Mac に Xcode と Node.js を入れ、このリポジトリを取ってくる
2. このフォルダで `npm install` → `npx cap add ios` → `npx capacitor-assets generate --ios`（アイコン）
3. `ios/App/App/Info.plist` に、次の説明を足す（ないと審査に通らない）
   - `NSLocationWhenInUseUsageDescription`：「今いる場所から、ごみの収集地区を探すために使います。位置情報はスマホの中だけで使い、外には送りません。」
   - `NSCameraUsageDescription`：「ごみを撮って、分け方を調べるために使います。写真はスマホの中だけで使い、外には送りません。」
4. `npm run ios` で Xcode が開くので、iPhone をつないで ▶

Mac がなくても、クラウドの Mac（Codemagic・GitHub Actions など）で作ることもできます。

## 中身を直したあと

```
npm run sync
```

`gomiappV3.1` の中身を写して、Android・iPhone のアプリに入れ直します。
収集日などのデータだけの更新なら、ストア版を出し直さなくても、公開ページ（GitHub Pages）を更新すれば届きます。

## ストアに出す前に決めること・すること

- **アプリの ID**（`capacitor.config.json` の `appId`。いまは仮に `io.github.you2rapid.gomicalendar`）。**一度ストアに出すと変えられない**ので、出す前に決める（例：自分のドメインを逆さにしたもの）
- **データの許可**：周南市（収集日）と光市（すべて）は、商用に使うには市の許可が必要（`gomiappV3.1/tools/munis/.../license.json`）。下松市はオープンデータなので、出典を書けばよい
- **ストアのアカウント**：Google Play（最初に 25ドル）、Apple Developer Program（年 99ドル）
- **プライバシーポリシーのページ**（公開ページに置く）と、ストアの「集めるデータ」の申告：集めるデータなし（位置情報・写真はスマホの中だけで使う。地区・設定もスマホの中だけ）
- **スクリーンショット**・アプリの説明（「市の公式アプリではありません」と書く）・問い合わせ先
- **売り方**（有料・広告・月額など）と、無料のブラウザ版をどうするか
- **署名の鍵**（Android の .jks）：Android Studio の「Build → Generate Signed App Bundle」で作る。**なくすとアプリを更新できなくなる**ので、GitHub に上げずに大事に保管する
- **公開ページの場所**：ストア版は `index.html` の `REMOTE`（いまは gomiappV3.1）からデータを読む。版のフォルダ名が変わってもストア版が読めるように、出す前に、データを置く決まった場所を決める
