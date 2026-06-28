# 金沢シニアレジデンス候補リスト

金沢市の県庁周辺エリアで、高齢者向け住宅へ転用できそうな一棟収益物件の候補リストを管理・公開するシステムです。

## ディレクトリ構成

```
kanazawa-senior/
├── data/
│   ├── properties.json   # 物件候補リスト本体
│   └── diff_log.csv      # 変更履歴
├── site/
│   └── index.html        # Webサイト（GitHub Pagesで公開）
└── .github/workflows/
    └── daily-update.yml  # 日次自動更新
```

## GitHub Pages 公開手順

1. このリポジトリを GitHub に push する
2. リポジトリの **Settings → Pages** を開く
3. **Source** を `Deploy from a branch` に設定
4. **Branch** を `main`、フォルダを `/site` に設定して Save
5. 数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開される

## GitHub Actions 設定（日次自動収集）

以下の Secrets をリポジトリに登録してください（Settings → Secrets and variables → Actions）。

| Secret名 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API キー |
| `LINE_NOTIFY_TOKEN` | LINE Notify トークン（通知先） |

日次実行は毎日 JST 06:00（UTC 21:00）に自動実行されます。  
手動実行は Actions タブ → "Daily Property Update" → "Run workflow" から可能です。

## 採点ルール（100点満点）

| 項目 | 配点 | 基準 |
|---|---|---|
| 県庁エリア適性 | 20点 | 鞍月・大友・直江・戸水を最上位 |
| 医療/生活利便 | 20点 | 県立中央病院・スーパー・バス停へのアクセス |
| 転用しやすさ | 20点 | 20〜40戸、RC/SRC/鉄骨、EVあり、2DK以上 |
| 取得可能性 | 20点 | 公開売出し中は高め |
| 収益/価格バランス | 20点 | 8,000万〜2億円、利回り8%以上 |

**優先度**: A=60点以上 / B=55〜59点 / C=45〜54点 / D=44点以下

## 注意事項

- AIが収集・採点した内容をもとに、問い合わせ・現地確認・登記などの実行動作に進む前には、**必ず原典URLを人間が確認**してください。
- スクレイピング規約に違反していないか、新しい検索元サイトを追加する際は都度確認してください。
- LINE通知トークン・APIキーなどの認証情報は、リポジトリに平文で含めないでください。
