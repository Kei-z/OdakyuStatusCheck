#!/usr/bin/env python3
"""
小田急の運行情報をチェックし、平常運転でない場合のみ LINE に通知する。
取得方法: Playwright(headless Chromium) で
         https://traininfo.odakyu-rt.jp/train_status を開き、
         JavaScript描画後のテキストを読んで判定する。
日本語表示・英語表示(WOVN)どちらでも判定できるようにする。
"""

import os
import re
import sys
from playwright.sync_api import sync_playwright

STATUS_URL = "https://traininfo.odakyu-rt.jp/train_status"

# 画面上部の総合メッセージが「平常」を示す語（日本語/英語）。
# どれかが含まれていれば平常運転とみなす。
NORMAL_TOP = [
    "平常どおり運転",
    "It's operating normally",
    "operating normally",
    "operating as normal",
]

# 異常を示す代表語（日本語/英語）。出ていれば通知する。
ABNORMAL_HINTS = [
    "見合わせ", "遅延", "遅れ", "運休", "ダイヤが乱れ", "直通運転を中止",
    "各駅停車のみ", "運転区間を変更",
    "suspended", "delay", "delayed", "altered schedule", "canceled",
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


def extract_top_message(text: str) -> str:
    """画面上部の『YYYY/MM/DD HH:MM ...』の行を1行抜き出す（通知用）。"""
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}", line):
            return line
    return ""


def judge(text: str):
    """(異常か, マッチ情報) を返す。

    判定方針：
    - 上部の総合メッセージ(top_normal)が「平常」を示していれば平常とみなす。
      これは小田急が状況に応じて出し分ける総合判定なので最も信頼できる。
    - 本文全体の異常語チェックは、固定リンク（例: "Proof of delay" 遅延証明書）や
      注意書き（"10分以上の遅れが…"）に常時ヒットして誤検知するため、
      主判定には使わない。top_normal が偽のときの参考情報としてのみ拾う。
    """
    top_normal = any(k in text for k in NORMAL_TOP)
    # 参考情報（通知文の補強用）。主判定には使わない。
    abnormal_hits = [w for w in ABNORMAL_HINTS if w in text]
    is_abnormal = not top_normal
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
    print(f"[DEBUG] LINE push status: {resp.status_code} / {resp.text[:200]}")
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
    top_msg = extract_top_message(text)

    # --- デバッグ出力（GitHub Actions ログ用。詳細はここだけ） ---
    print("=" * 60)
    print(f"[DEBUG] URL : {STATUS_URL}")
    print(f"[DEBUG] body length : {len(text)} chars")
    print(f"[DEBUG] judge info  : {info}")
    print(f"[DEBUG] is_abnormal : {is_abnormal}")
    print(f"[DEBUG] top message : {top_msg}")
    print("=" * 60)
    # --------------------------------------------------------

    if test_notify:
        notify_line("✅ テスト通知です。LINE連携は正常に動いています。")
        print("Test notification sent.")
        return

    # 平常・異常にかかわらず毎回通知する。
    body = top_msg if top_msg else "運行状況を取得しました。"
    if is_abnormal:
        head = "🚃⚠️ 小田急に運行情報あり（遅延・運休などの可能性）"
    else:
        head = "🚃✅ 小田急は平常運転です"

    notify_line(
        f"{head}\n"
        f"{body}\n"
        f"{STATUS_URL}"
    )
    print(f"Notified. abnormal={is_abnormal}")


if __name__ == "__main__":
    main()
