#!/usr/bin/env python3
"""金沢シニアレジデンス候補リスト 日次自動収集スクリプト"""

import json
import csv
import os
import smtplib
import sys
from datetime import date
from email.mime.text import MIMEText
import anthropic

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PROPERTIES_FILE = os.path.join(DATA_DIR, 'properties.json')
DIFF_LOG_FILE = os.path.join(DATA_DIR, 'diff_log.csv')

PROMPT = """
あなたは金沢市の不動産情報収集エージェントです。
以下のタスクを実行してください。

## 対象エリア（Sランク優先）
鞍月、大友、直江、戸水、藤江北、無量寺、畝田、北町、駅西新町、西念、駅西本町、諸江、問屋町

## 対象種別
一棟マンション、一棟アパート、売ビル、売寮、元社員寮、元社宅、元ホテル、元介護施設

## 収集先サイト（robots.txtに従い通常閲覧の範囲で）
1. さくらホーム: https://www.sakura-home.co.jp/purchase/list/kind_other_kanazawa_c.html
2. 楽待（石川県）: https://www.rakumachi.jp/syuuekibukken/area/prefecture/dimAll/?area%5B%5D=17201
3. 健美家（石川県）: https://www.kenbiya.com/ar/ls/ishikawa/
4. アットホーム投資: https://toushi-athome.jp/%E9%87%91%E6%B2%A2%E5%B8%82/

## 採点ルール（100点満点）
- 県庁エリア適性: 20点（鞍月・大友・直江・戸水が最高）
- 医療/生活利便: 20点（県立中央病院・スーパー・バス停アクセス）
- 転用しやすさ: 20点（20〜40戸・RC/鉄骨・EV・2DK以上）
- 取得可能性: 20点（公開売出し中が高い）
- 収益/価格バランス: 20点（8000万〜2億・利回り8%以上）

## タスク
1. 上記サイトを検索し、対象エリア×対象種別の物件を収集する
2. 各物件を採点する
3. 以下のJSON形式で結果を出力する（```json で囲む）

出力フォーマット:
```json
{
  "new_properties": [
    {
      "name": "物件名",
      "area": "エリア",
      "address": "所在地",
      "type": "種別",
      "price_man_yen": 数値またはnull,
      "yield_pct": 数値またはnull,
      "units": 数値またはnull,
      "built_year": 数値またはnull,
      "structure": "構造",
      "elevator": "有/無/要確認",
      "score_prefecture_area": 数値,
      "score_medical_living": 数値,
      "score_conversion": 数値,
      "score_acquirability": 数値,
      "total_score": 数値,
      "priority": "A/B/C/D",
      "next_action": "次のアクション",
      "notes": "メモ",
      "source_url": "URL",
      "status": "公開中"
    }
  ],
  "summary": "本日の収集サマリー（新規n件発見、注目物件の概要）"
}
```

既存物件リスト（照合用）はシステムから提供されます。
新規物件のみ new_properties に含めてください。
"""


def load_properties():
    with open(PROPERTIES_FILE, encoding='utf-8') as f:
        return json.load(f)


def save_properties(props):
    with open(PROPERTIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(props, f, ensure_ascii=False, indent=2)


def append_diff_log(rows):
    today = date.today().isoformat()
    with open(DIFF_LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([today] + row)


def should_notify(prop):
    if prop.get('total_score', 0) >= 60:
        return True
    if prop.get('score_prefecture_area', 0) >= 18:
        return True
    price = prop.get('price_man_yen')
    units = prop.get('units')
    if price and units and price <= 20000 and units >= 20:
        return True
    return False


def send_gmail(subject, body):
    user = os.environ.get('GMAIL_USER')
    password = os.environ.get('GMAIL_APP_PASSWORD')
    if not user or not password:
        print("Gmail設定なし、通知スキップ")
        return
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = user
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print("メール送信完了")
    except Exception as e:
        print(f"メール送信失敗: {e}")


def run():
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    existing = load_properties()
    existing_names = {p['name'] for p in existing}
    existing_urls = {p.get('source_url') for p in existing if p.get('source_url')}

    system_context = f"既存物件数: {len(existing)}件\n既存物件名: {', '.join(list(existing_names)[:10])}..."

    print("Claude API呼び出し中...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_context,
        messages=[{"role": "user", "content": PROMPT}],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10
        }]
    )

    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text

    print("レスポンス取得完了")

    new_props = []
    summary = "本日は新規物件の検出なし"

    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            new_props = data.get('new_properties', [])
            summary = data.get('summary', summary)
        except json.JSONDecodeError as e:
            print(f"JSON解析エラー: {e}")

    today = date.today().isoformat()
    diff_rows = []
    notify_props = []
    next_no = max((p['no'] for p in existing), default=0) + 1

    for prop in new_props:
        if prop.get('source_url') in existing_urls:
            continue
        if prop.get('name') in existing_names:
            continue
        prop['no'] = next_no
        prop['category'] = '公開売出し'
        prop['first_detected_at'] = today
        prop['last_updated_at'] = today
        existing.append(prop)
        existing_names.add(prop['name'])
        if prop.get('source_url'):
            existing_urls.add(prop['source_url'])
        next_no += 1
        diff_rows.append([prop['name'], '新規', prop.get('price_man_yen', ''), '', prop.get('source_url', ''), ''])
        if should_notify(prop):
            notify_props.append(prop)

    if new_props:
        save_properties(existing)
        print(f"properties.json 更新: {len(new_props)}件追加")

    if diff_rows:
        append_diff_log(diff_rows)

    notify_lines = [f"【金沢シニアレジデンス】{today} 日次更新レポート\n"]
    notify_lines.append(summary)
    notify_lines.append(f"\n新規追加: {len(new_props)}件")

    if notify_props:
        notify_lines.append("\n⚡ 注目物件:")
        for p in notify_props:
            notify_lines.append(f"  - {p['name']} ({p.get('area','')}): {p.get('total_score',0)}点/{p.get('priority','')}優先")
            if p.get('source_url'):
                notify_lines.append(f"    {p['source_url']}")

    notify_body = '\n'.join(notify_lines)
    print(notify_body)

    subject = f"【金沢シニアレジデンス】{today} 更新: 新規{len(new_props)}件"
    send_gmail(subject, notify_body)

    print(f"\n完了: 新規{len(new_props)}件")
    return len(new_props)


if __name__ == '__main__':
    count = run()
    sys.exit(0)
