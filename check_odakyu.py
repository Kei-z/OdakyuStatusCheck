#!/usr/bin/env python3
"""
小田急の運行情報をチェックし、平常運転でない場合のみ LINE に通知する。
取得方法: Playwright(headless Chromium) で
         https://traininfo.odakyu-rt.jp/train_status を開き、
         JavaScript描画後のテキストを読んで判定する。
日本語・英語どちらの表示でも判定できるようにしている。
"""

import os
import sys
from playwright.sync_api import sync_playwright

STATUS_URL = "https://traininfo.odakyu-rt.jp/train_status"

# 画面上部の総合メッセージが「平常」を示す表現（日英）。
NORMAL_TOP_KEYWORDS = [
    "平常どおり運転",          # 日本語
    "operating normally",     # 英語: It's operating normally.
]

# 異常を示す代表語（日英）。1つでも出ていれば異常とみなす。
ABNORMAL_HINTS = [
    # 日本語
    "見合わせ", "遅延", "遅れ", "運休", "ダイヤが乱れ", "直通運転を中止",
    "各駅停車のみ", "運転区間を変更",
    # 英語
    "suspended", "delay", "delayed", "Canceled direct", "altered schedule",
    "Local trains only",
]


def fetch_text():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        )
        page.goto(STATUS_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        text = page.inner_text("body")
        browser.close()
    return text


def judge(text: str):
    """(異常か, マッチ情報) を返す。"""
    lower = text.lower()
    top_normal = any(
        (kw.lower() in lower) for kw in NORMAL_TOP_KEYWORDS
    )
    abnormal_hits = [w for w in ABNORMAL_HINTS if w.lower() in lower]

    # トップが平常表示で、異常語がなければ平常。
    is_abnormal = (not top_normal) or bool(abnormal_hits)
    return is_abnormal, {"top_normal": top_normal, "abnormal_hits": abnormal_hits}


def notify_line(message: str):
    import requests
    token = os.environ["LINE_TOKEN"]
    user_id = os.environ["LINE_USER_ID"]
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": message}]},
        timeout=15,
    )
    resp.raise_for_status()


def main():
    test_notify = os.environ.get("TEST_NOTIFY") == "1"

    try:
        text = fetch_text()
    except Exception as e:
        print(f"[ERROR] fetch failed: {e}")
        notify_line(f"⚠️ 小田急の運行情報を取得できませんでした。手動で確認してください。\n{STATUS_URL}\n({e})")
        sys.exit(0)

    is_abnormal, info = judge(text)

    # 簡潔なデバッグ出力（Actionsログ用。LINEには送らない）
    print(f"[DEBUG] judge info  : {info}")
    print(f"[DEBUG] is_abnormal : {is_abnormal}")

    if test_notify:
        notify_line("✅ テスト通知です。LINE連携は正常に動いています。")
        print("Test notification sent.")
        return

    if is_abnormal:
        snippet = text[:300]
        notify_line(
            "🚃 小田急に運行情報あり（遅延・運休などの可能性）。\n"
            "出発前に確認してください。\n"
            f"{STATUS_URL}\n\n"
            f"---\n{snippet}"
        )
        print("Abnormal: notified.")
    else:
        print("Normal: no notification.")


if __name__ == "__main__":
    main()
