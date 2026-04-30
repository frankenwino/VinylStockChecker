"""
Delete all messages in a Discord channel.

Extracts the channel ID from DISCORD_WEBHOOK_URL in .env, then uses
DISCORD_BOT_TOKEN from .env to bulk-delete messages (≤14 days old) and
individually delete older ones.

Usage:
    python delete_discord_messages.py
"""

import sys
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


def extract_channel_id(webhook_url: str) -> str:
    """Get the channel ID by querying the webhook — the ID in the URL is the
    webhook's own ID, not the channel it posts to."""
    try:
        resp = requests.get(webhook_url)
        resp.raise_for_status()
        channel_id = resp.json().get("channel_id", "")
        if channel_id:
            print(f"Resolved channel ID from webhook: {channel_id}")
        return channel_id
    except requests.RequestException as e:
        print(f"Error querying webhook: {e}")
        return ""


def fetch_messages(channel_id: str, headers: dict, before: str = None) -> list:
    """Fetch up to 100 messages, optionally before a given message ID."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    params = {"limit": 100}
    if before:
        params["before"] = before
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def bulk_delete(channel_id: str, message_ids: list, headers: dict):
    """Bulk-delete up to 100 messages (must all be <14 days old)."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/bulk-delete"
    resp = requests.post(url, headers=headers, json={"messages": message_ids})
    resp.raise_for_status()


def single_delete(channel_id: str, message_id: str, headers: dict):
    """Delete a single message (used for messages older than 14 days)."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    resp = requests.delete(url, headers=headers)
    resp.raise_for_status()


def main():
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        print("Error: DISCORD_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not found in .env")
        sys.exit(1)

    channel_id = extract_channel_id(WEBHOOK_URL)
    if not channel_id or not channel_id.isdigit():
        print(f"Error: Could not extract a valid channel ID from webhook URL: {WEBHOOK_URL}")
        sys.exit(1)

    print(f"Channel ID: {channel_id}")

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json",
    }

    # 14-day cutoff as a snowflake ID (Discord snowflake encodes timestamp)
    cutoff_ms = (time.time() - 14 * 24 * 60 * 60) * 1000
    cutoff_snowflake = int((cutoff_ms - 1420070400000) * 4194304)

    total_deleted = 0
    before = None

    print("Fetching and deleting messages...")

    while True:
        try:
            messages = fetch_messages(channel_id, headers, before)
        except requests.HTTPError as e:
            print(f"Error fetching messages: {e.response.status_code} {e.response.text}")
            sys.exit(1)

        if not messages:
            break

        print(f"  Fetched {len(messages)} messages")

        bulk_ids = []
        old_ids = []

        for msg in messages:
            msg_id = msg["id"]
            if int(msg_id) > cutoff_snowflake:
                bulk_ids.append(msg_id)
            else:
                old_ids.append(msg_id)

        # Bulk delete recent messages (API requires at least 2 for bulk-delete)
        if len(bulk_ids) >= 2:
            try:
                bulk_delete(channel_id, bulk_ids, headers)
                total_deleted += len(bulk_ids)
                print(f"  Bulk deleted {len(bulk_ids)} messages")
                time.sleep(1)  # respect rate limits
            except requests.HTTPError as e:
                print(f"  Bulk delete failed: {e.response.status_code} {e.response.text}")
                # Fall back to individual deletion
                old_ids.extend(bulk_ids)
        elif len(bulk_ids) == 1:
            # Can't bulk-delete a single message
            old_ids.extend(bulk_ids)

        # Individually delete old messages (>14 days) or bulk-delete fallbacks
        for msg_id in old_ids:
            try:
                single_delete(channel_id, msg_id, headers)
                total_deleted += 1
                print(f"  Deleted message {msg_id}")
                time.sleep(0.5)  # slower to avoid rate limits on individual deletes
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = e.response.json().get("retry_after", 1)
                    print(f"  Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    # Retry once
                    try:
                        single_delete(channel_id, msg_id, headers)
                        total_deleted += 1
                    except requests.HTTPError:
                        print(f"  Failed to delete message {msg_id}, skipping")
                else:
                    print(f"  Failed to delete message {msg_id}: {e.response.status_code}")

        before = messages[-1]["id"]

    print(f"\nDone. Deleted {total_deleted} messages.")


if __name__ == "__main__":
    main()
