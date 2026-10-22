"""English texts. Markup — HTML (parse_mode=HTML)."""

TEXTS: dict[str, str] = {
    # --- language
    "choose_language": "🌐 Выберите язык / Choose your language:",
    "language_set": "✅ Language: English",

    # --- welcome & privacy
    "welcome": (
        "👋 Hi, <b>{name}</b>!\n\n"
        "I let you know when someone <b>deletes a message</b> in your private chats and show what it said.\n\n"
        "<b>How to connect:</b>\n"
        "Telegram Settings → <b>Telegram Business</b> → <b>Chatbots</b> → "
        "enter @{bot_username} and choose the chats.\n"
        "(Telegram Premium is required.)\n\n"
        "{privacy}"
    ),
    "privacy": (
        "🔒 <b>Privacy</b>\n"
        "• The bot works only in chats of the account that connected it.\n"
        "• On deletion it reports the author (@username, ID), chat, time and the <b>text</b> of the message.\n"
        "• To do that, incoming message text is stored temporarily and erased right after "
        "the notice (or after the retention period).\n"
        "• Photos and videos are <b>saved to your computer</b> so they can be shown if the sender "
        "deletes the message. Data is stored locally and sent nowhere else. View-once media is "
        "never delivered to bots by Telegram at all.\n"
        "• You are responsible for how you use the bot."
    ),
    "trial_started": "🎁 Your free trial for <b>{days} days</b> is now active.",
    "menu_title": "📋 <b>Main menu</b>",

    # --- buttons
    "btn_status": "📊 Status",
    "btn_settings": "⚙️ Settings",
    "settings_title": "⚙️ <b>Settings</b>",
    "btn_buy": "💳 Subscription",
    "btn_buy_short": "💳 Buy",
    "btn_lang": "🌐 Language",
    "btn_help": "❓ Help",
    "btn_stop": "⛔ Stop",
    "btn_resume": "▶️ Resume",
    "btn_back": "⬅️ Back",
    "btn_stop_confirm": "✅ Yes, stop",

    # --- status
    "status_title": "📊 <b>Status</b>",
    "status_sub_active": "💎 Subscription: <b>active</b> ({plan})\n📅 Until: <b>{until}</b>",
    "status_sub_lifetime": "💎 Subscription: <b>lifetime</b> ♾",
    "status_sub_expired": "⌛️ Subscription: <b>expired</b> {until}",
    "status_sub_none": "⌛️ Subscription: <b>none</b>",
    "status_conn_on": "🔗 Business connection: <b>active</b>",
    "status_conn_off": "🔗 Business connection: <b>disabled</b>",
    "status_conn_none": (
        "🔗 Business connection: <b>none</b>\n"
        "Connect: Settings → Telegram Business → Chatbots → @{bot_username}"
    ),
    "status_notif_on": "🔔 Notifications: <b>on</b>",
    "status_notif_off": "🔕 Notifications: <b>paused</b>",

    # --- plans
    "plan_trial": "free trial",
    "plan_m1": "30 days",
    "plan_m3": "90 days",
    "plan_y1": "1 year",
    "plan_life": "lifetime",
    "plan_grant": "granted by admin",
    "buy_title": "💳 <b>Choose a plan</b>\nPayment — Telegram Stars ⭐",
    "plan_button": "{name} — {stars} ⭐",
    "invoice_title": "Subscription: {name}",
    "invoice_description": "Notifications about deleted messages in your business chats. Plan: {name}.",
    "invoice_label": "Subscription ({name})",
    "invoice_sent": "🧾 Invoice created — pay it with the button below.",
    "payment_success": "✅ Payment received! Subscription is active until <b>{until}</b>.",
    "payment_success_lifetime": "✅ Payment received! Subscription is active <b>forever</b> ♾",
    "precheckout_error": "Could not verify the invoice. Please request a new one via «💳 Buy».",
    "payment_refunded": "↩️ Refund of {amount} ⭐ completed. Your subscription has been adjusted.",

    # --- help
    "help": (
        "❓ <b>Help</b>\n\n"
        "1. Connect the bot: Settings → Telegram Business → Chatbots → @{bot_username}.\n"
        "2. Choose which chats the bot can access.\n"
        "3. When someone deletes a message, I'll send you a notice: author, chat, sent time "
        "and deletion time.\n\n"
        "ℹ️ Notes:\n"
        "• Only messages received <b>after</b> connecting the bot are tracked.\n"
        "• Telegram doesn't tell who deleted a message — its author is shown.\n"
        "• Your own messages are not reported.\n"
        "• Text and metadata are kept for at most {retention} days and erased after the notice.\n\n"
        "💳 Payments and refunds: /paysupport\n\n"
        "{privacy}"
    ),
    "paysupport": (
        "💬 <b>Payment support</b>\n"
        "If something went wrong with a payment or you want a refund, contact the administrator "
        "and include your ID: <code>{user_id}</code>."
    ),

    # --- stop / resume
    "stop_confirm": (
        "⛔ Stop notifications?\n"
        "Stored metadata of your chats will be deleted. Your subscription stays intact."
    ),
    "stopped": (
        "⛔ Notifications stopped, metadata deleted ({count} records).\n\n"
        "To fully disconnect the bot: Settings → Telegram Business → Chatbots → remove the bot."
    ),
    "resumed": "▶️ Notifications are on again.",

    # --- business connection
    "connected": (
        "🔗 <b>The bot is connected to your account!</b>\n"
        "I'll let you know when someone deletes a message in the chats I can access."
    ),
    "disconnected": "🔌 The bot was disconnected. Your data is kept — it will be restored when you reconnect.",

    # --- deletion notices
    "deleted_single": "🗑 <b>Message deleted</b>\n\n{entry}",
    "deleted_multi": "🗑 <b>Messages deleted: {count}</b>\n\n{entries}",
    "deleted_entry": (
        "👤 Author: {author}\n"
        "💬 Chat: {chat}\n"
        "📨 Sent: {sent}\n"
        "🗑 Deleted: {deleted}"
    ),
    "deleted_unknown": "🗑 Message deleted (sender details unavailable)\n💬 Chat: {chat}\n🗑 Deleted: {deleted}",
    "deleted_unknown_entry": "❔ Sender details unavailable\n💬 Chat: {chat}\n🗑 Deleted: {deleted}",
    # Content hidden under a spoiler inside a quote — reveals on tap
    "content_quote": "<blockquote><tg-spoiler>{text}</tg-spoiler></blockquote>",
    "watermark": "\n\n<a href=\"https://t.me/{bot}\">@{bot}</a>",
    "del_head": "🗑 <b>{author}</b> deleted a message",
    "del_head_media": "📷 <b>{author}</b> deleted media",
    "del_time": "🕒 {sent} → 🗑 {deleted}",
    "deleted_unknown_compact": "🗑 Deleted messages: {count} (details unavailable) · {deleted}",
    "deleted_more_compact": "… and {count} more",
    "edit_head": "✏️ <b>{author}</b> edited a message",
    "edit_time": "🕒 {edited}",
    "edit_old_label": "Before:",
    "edit_new_label": "After:",
    "edit_old_unavailable": "<i>previous version unavailable</i>",
    "deleted_no_text": "📎 Attachment: {type}",
    "deleted_media_caption": "🗑 Deleted media\n⤷ {author}\n⏱ {deleted}",
    "deleted_media_unavailable": "📎 Media ({count}) is no longer available — Telegram won't return the file.",
    "deleted_more": "…and {count} more",

    # --- subscription expired
    "sub_expired_reminder": (
        "⌛️ <b>Your subscription has expired.</b>\n"
        "Deleted-message notifications are paused. Renew to receive them again."
    ),

    # --- admin
    "admin_stats": (
        "📈 <b>Statistics</b>\n"
        "👥 Users: <b>{users}</b>\n"
        "💎 Active subscriptions: <b>{active_subs}</b> (paid: {paid_subs})\n"
        "🔗 Active connections: <b>{connections}</b>\n"
        "⭐ Stars received: <b>{stars}</b>\n"
        "🗂 Metadata records: <b>{messages_meta}</b>"
    ),
    "admin_grant_usage": "Usage: <code>/grant &lt;user_id&gt; &lt;days|forever&gt;</code>",
    "admin_extend_usage": "Usage: <code>/extend &lt;user_id&gt; &lt;days|forever&gt;</code>",
    "admin_revoke_usage": "Usage: <code>/revoke &lt;user_id&gt;</code>",
    "admin_revoke_ok": "⛔ Subscription for <code>{user_id}</code> revoked.",
    "admin_revoke_none": "❌ User <code>{user_id}</code> has no subscription.",
    "admin_subinfo_usage": "Usage: <code>/subinfo &lt;user_id&gt;</code>",
    "admin_subinfo_active": "💎 Active ({plan}), until <b>{until}</b>",
    "admin_subinfo_inactive": "⌛️ Inactive (expired {until})",
    "admin_subinfo": (
        "👤 <b>User</b> <code>{user_id}</code>\n"
        "{sub}\n"
        "🔗 Connections: <b>{conn_active}</b> active of {conn_total}\n"
        "🗂 Metadata records: <b>{messages}</b>"
    ),
    "admin_users_empty": "No users.",
    "admin_users_title": "👥 <b>Users</b> (shown: {count})",
    "admin_backup_ok": "💾 Backup created: <code>{path}</code> (~{size} KB)",
    "admin_backup_file": "Database backup",
    "admin_backup_error": "❌ Backup failed: <code>{error}</code>",
    "admin_grant_ok": "✅ User <code>{user_id}</code> got {days} days. Valid until <b>{until}</b>.",
    "admin_grant_notify": "🎁 The administrator granted you a {days}-day subscription. Valid until <b>{until}</b>.",
    "admin_refund_usage": (
        "Usage: <code>/refund &lt;telegram_payment_charge_id&gt;</code>\n"
        "List payments: <code>/payments [user_id]</code>"
    ),
    "admin_refund_ok": "↩️ Payment <code>{charge_id}</code> refunded ({amount} ⭐).",
    "admin_refund_not_found": "❌ Payment not found or already refunded.",
    "admin_refund_error": "❌ Telegram rejected the refund: <code>{error}</code>",
    "admin_payments_empty": "No payments.",
    "admin_payments_title": "🧾 <b>Recent payments</b>",

    # --- errors
    # --- history and connect
    "btn_history": "🕓 History",
    "btn_connect": "🔗 Connect",
    "history_title": "🕓 <b>Message history</b>",
    "history_empty": "No saved records yet.\nThey appear once messages arrive in the connected chats.",
    "history_page_header": "Page {page}/{pages} · {total} total",
    "history_filter_q": "🔎 Search: <code>{q}</code>",
    "btn_hist_all": "♻️ All",
    "btn_hist_7d": "🗓 7d",
    "btn_hist_30d": "🗓 30d",
    "btn_hist_deleted": "🗑 Deleted",
    "btn_hist_search": "🔎 Search",
    "history_search_prompt": "🔎 Send text to search your saved messages:",
    "history_item_gone": "Record not found.",
    "history_status_deleted": "deleted",
    "history_status_active": "present",
    "history_item_title": "🗒 <b>Record</b>",
    "history_item_when": "🕒 Sent: {when} ({status})",
    "history_item_deleted": "🗑 Deleted: {when}",
    "history_item_text": "<blockquote>{text}</blockquote>",
    "history_item_media": "📎 Attachment: {type}",
    "history_item_media_caption": "🗒 From your history",
    "history_item_media_gone": "📎 Media is no longer available — Telegram won't return the file.",
    "connect_guide": (
        "🔗 <b>Connect in 3 steps</b>\n\n"
        "1. Telegram Settings → <b>Telegram Business</b> → <b>Chatbots</b>\n"
        "2. Add the bot:  <code>@{bot_username}</code>  (tap to copy)\n"
        "3. Enable <b>“Manage messages”</b> access and save\n\n"
        "Done — the bot starts sending alerts. Telegram Premium is required."
    ),
    "btn_connect_open": "👉 Open the bot",
    "error_generic": "⚠️ Something went wrong. Please try again later.",
}
