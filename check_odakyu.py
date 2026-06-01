#!/usr/bin/env python3
"""
小田急の運行情報をチェックし、平常運転でない場合のみ LINE に通知する。
（デバッグ版：取得内容と判定結果を毎回ログに出力する）
"""

import os
import sys
import requests

ODAKYU_STATUS_URL = "https://www.odakyu.jp/cgi/json/unkou_info.json"
NORMAL_KEYWORDS = ["平常", "通常", "現在、事故", "情報はありません"]


def fetch_status():
    headers = {"User-Agent": "Mozilla/5.0 (odakyu-status-checker)"}
    resp = requests.get(ODAKYU_STATUS_URL, headers=headers, timeout=15)

    # --- デバッグ出力 ---
    print("=" * 60)
    print(f"[DEBUG] URL          : {ODAKYU_STATUS_URL}")
    print(f"[DEBUG] HTTP status  : {resp.status_code}")
    print(f"[DEBUG] Content-Type : {resp.headers.get('Content-Type')}")
    print(f"[DEBUG] Body length  : {len(resp.text)} chars")
    print("[DEBUG] Body (first 1000 chars):")
    print(resp.text[:1000])
    print("=" * 60)
    # -------------------

    resp.raise_for_status()

    try:
        data = resp.json()
        text = str(data)
    except ValueError:
        text = resp.text

    matched = [kw for kw in NORMAL_KEYWORDS if kw in text]
    is_abnormal = len(matched) == 0

    print(f"[DEBUG] Matched normal keywords: {matched}")
    print(f"[DEBUG] Judged abnormal? : {is_abnormal}")

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
        json={"to": user_id, "messages": [{"type": "text", "text": message}]},
        timeout=15,
    )
    print(f"[DEBUG] LINE push status: {resp.status_code} / {resp.text[:200]}")
    resp.raise_for_status()


def main():
    # テスト通知用フラグ。環境変数 TEST_NOTIFY=1 を付けると必ず1通送る。
    test_notify = os.environ.get("TEST_NOTIFY") == "1"

    try:
        is_abnormal, text = fetch_status()
    except Exception as e:
        print(f"[ERROR] fetch failed: {e}")
        notify_line(f"⚠️ 小田急の運行情報を取得できませんでした。手動で確認してください。\n({e})")
        sys.exit(0)

    if test_notify:
        notify_line("✅ テスト通知です。LINE連携は正常に動いています。")
        print("Test notification sent.")
        return

    if is_abnormal:
        snippet = text[:300]
        notify_line(
            "🚃 小田急に運行情報あり（遅延・運休の可能性）。\n"
            "出発前に確認してください。\n"
            "https://www.odakyu.jp/emergency/\n\n"
            f"---\n{snippet}"
        )
        print("Abnormal: notified.")
    else:
        print("Normal: no notification.")


if __name__ == "__main__":
    main()
