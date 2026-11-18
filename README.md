# ごみ分別ナビ（周南市・非公式）

周南市「家庭ごみの分別方法（令和6年4月改定版）」の分別早見表をもとにした、ごみの分別検索アプリです。
スマホのホーム画面に追加して、アプリのように使えます（PWA・オフライン対応）。

> 非公式ツールです。最新の情報や収集日は、お住まいの地域のごみ収集カレンダーや市ホームページで確認してください。

## 公開のしかた（GitHub Pages）

1. GitHub Desktop で **File → Add local repository** を選び、このフォルダを追加する
2. **Publish repository** を押す（「Keep this code private」のチェックは**外す**。無料プランの Pages は公開リポジトリのみ）
3. github.com でそのリポジトリを開き、**Settings → Pages** で
   Source を「Deploy from a branch」、Branch を「main」「/(root)」にして **Save**
4. 数分後、`https://<ユーザー名>.github.io/<リポジトリ名>/` で開けるようになる

## スマホへの追加

- **iPhone**：Safari で上のURLを開き、共有ボタン →「ホーム画面に追加」
- **Android**：Chrome で上のURLを開き、メニュー（︙）→「ホーム画面に追加」または「アプリをインストール」

一度開けば、電波がなくても使えます。

## 更新のしかた

ファイルを直したら、GitHub Desktop で Commit → **Push origin**。
次にスマホでアプリを開いたとき（ネット接続時）に新しい版へ切り替わります。

## ファイル構成

| ファイル | 内容 |
| --- | --- |
| `index.html` | アプリ本体（品目データも埋め込み済み） |
| `manifest.webmanifest` | ホーム画面に追加するための設定 |
| `sw.js` | オフライン対応（Service Worker） |
| `icons/` | アプリアイコン |
| `tools/extract_items.py` | 冊子PDFから品目データを作り直し、`index.html` に書き込む |
| `tools/make_icons.py` | アイコン画像を作り直す |

冊子が改定されたら、PDFを置いて次を実行します（要 `pip install pymupdf pykakasi`）。

```
python tools/extract_items.py 104994.pdf items.json warn.txt index.html
```
