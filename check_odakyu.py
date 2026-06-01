#!/usr/bin/env python3
"""
小田急の運行情報をチェックし、平常運転でない場合のみ LINE に通知する。
取得先: https://traininfo.odakyu-rt.jp/train_status （HTMLを取得して判定）
デバッグ版：取得内容と判定結果を毎回ログに出力する。
"""

import os
import sys
import re
import requests

STATUS_URL = "https://traininfo.odakyu-rt.jp/train_status"

# 「平常運転」を示す文言。実際のHTMLを見て調整する。
NORMAL_KEYWORDS = ["平常どおり運転", "平常運転", "平常通り運転"]


def fetch_status():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    resp = requests.get(STATUS_URL, headers=headers, timeout=15)

    # HTMLタグを大まかに除去して、本文テキストだけ見やすくする
    body = resp.text
    text_only = re.sub(r"<script[\s\S]*?</script>", " ", body)
    text_only = re.sub(r"<style[\s\S]*?</style>", " ", text_only)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    text_only = re.sub(r"\s+", " ", text_only).strip()

    # --- デバッグ出力 ---
    print("=" * 60)
    print(f"[DEBUG] URL          : {STATUS_URL}")
    print(f"[DEBUG] HTTP status  : {resp.status_code}")
    print(f"[DEBUG] Content-Type : {resp.headers.get('Content-Type')}")
    print(f"[DEBUG] Body length  : {len(body)} chars")
    print("[DEBUG] Text-only (first 1500 chars):")
    print(text_only[:1500])
    print("=" * 60)
    # -------------------

    resp.raise_for_status()

    matched = [kw for kw in NORMAL_KEYWORDS if kw in body]
    is_abnormal = len(matched) == 0

    print(f"[DEBUG] Matched normal keywords: {matched}")
    print(f"[DEBUG] Judged abnormal? : {is_abnormal}")

    return is_abnormal, text_only


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
    test_notify = os.environ.get("TEST_NOTIFY") == "1"

    try:
        is_abnormal, text = fetch_status()
    except Exception as e:
        print(f"[ERROR] fetch failed: {e}")
        notify_line(f"⚠️ 小田急の運行情報を取得できませんでした。手動で確認してください。\n{STATUS_URL}\n({e})")
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
            f"{STATUS_URL}\n\n"
            f"---\n{snippet}"
        )
        print("Abnormal: notified.")
    else:
        print("Normal: no notification.")


if __name__ == "__main__":
    main()
