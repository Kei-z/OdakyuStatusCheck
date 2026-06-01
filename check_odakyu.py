#!/usr/bin/env python3
"""
小田急の運行情報をチェックし、平常運転でない場合のみ LINE に通知する。
GitHub Actions の cron から平日朝に起動される想定。
"""

import os
import sys
import requests

# 小田急の運行情報ページ（公式）。仕様変更があれば URL / 抽出ロジックの調整が必要。
ODAKYU_STATUS_URL = "https://www.odakyu.jp/cgi/json/unkou_info.json"

# 平常運転を示すと思われるキーワード。実際のレスポンスを見て調整する。
NORMAL_KEYWORDS = ["平常", "通常", "現在、事故", "情報はありません"]


def fetch_status():
    """運行情報を取得して (異常かどうか, 本文) を返す。"""
    headers = {"User-Agent": "Mozilla/5.0 (odakyu-status-checker)"}
    resp = requests.get(ODAKYU_STATUS_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    # JSON でない / 構造が違う場合に備えてテキストとしても扱える形にする
    try:
        data = resp.json()
        text = str(data)
    except ValueError:
        text = resp.text

    is_abnormal = not any(kw in text for kw in NORMAL_KEYWORDS)
    return is_abnormal, text


def notify_line(message: str):
    token = os.environ["LINE_TOKEN"]
    user_id = os.environ["LINE_USER_ID"]

    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=15,
    )
    resp.raise_for_status()


def main():
    try:
        is_abnormal, text = fetch_status()
    except Exception as e:
        # 取得に失敗したら、念のため通知（チェックできない＝自分で確認すべき）
        notify_line(f"⚠️ 小田急の運行情報を取得できませんでした。手動で確認してください。\n({e})")
        sys.exit(0)

    if is_abnormal:
        # 必要なら text を整形して載せる。長すぎる場合は切り詰め。
        snippet = text[:300]
        notify_line(
            "🚃 小田急に運行情報あり（遅延・運休の可能性）。\n"
            "出発前に確認してください。\n"
            "https://www.odakyu.jp/emergency/\n\n"
            f"---\n{snippet}"
        )
        print("Abnormal: notified.")
    else:
        # 平常運転なら何もしない（通知で邪魔しない）
        print("Normal: no notification.")


if __name__ == "__main__":
    main()
