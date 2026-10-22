"""Русские тексты. Разметка — HTML (parse_mode=HTML)."""

TEXTS: dict[str, str] = {
    # --- язык
    "choose_language": "🌐 Выберите язык / Choose your language:",
    "language_set": "✅ Язык: русский",

    # --- приветствие и приватность
    "welcome": (
        "👋 Привет, <b>{name}</b>!\n\n"
        "Я сообщаю, когда собеседник <b>удаляет сообщение</b> в ваших личных чатах, и показываю, что там было написано.\n\n"
        "<b>Как подключить:</b>\n"
        "Настройки Telegram → <b>Telegram для бизнеса</b> → <b>Чат-боты</b> → "
        "введите @{bot_username} и выберите чаты.\n"
        "(Нужен Telegram Premium.)\n\n"
        "{privacy}"
    ),
    "privacy": (
        "🔒 <b>Приватность</b>\n"
        "• Бот работает только в чатах аккаунта, который сам его подключил.\n"
        "• При удалении сообщается автор (@тег, ID), чат, время и <b>текст</b> удалённого сообщения.\n"
        "• Для этого текст входящих сообщений временно хранится и стирается сразу после "
        "уведомления (или через срок хранения).\n"
        "• Фото и видео <b>сохраняются на ваш компьютер</b>, чтобы показать их, если собеседник "
        "удалит сообщение. Данные хранятся локально и никуда не передаются. Одноразовые "
        "(view-once) медиа Telegram ботам не отдаёт вовсе.\n"
        "• Ответственность за использование бота лежит на пользователе."
    ),
    "trial_started": "🎁 Вам активирован бесплатный пробный период на <b>{days} дн.</b>",
    "menu_title": "📋 <b>Главное меню</b>",

    # --- кнопки
    "btn_status": "📊 Статус",
    "btn_settings": "⚙️ Настройки",
    "settings_title": "⚙️ <b>Настройки</b>",
    "btn_buy": "💳 Подписка",
    "btn_buy_short": "💳 Купить",
    "btn_lang": "🌐 Язык",
    "btn_help": "❓ Помощь",
    "btn_stop": "⛔ Стоп",
    "btn_resume": "▶️ Возобновить",
    "btn_back": "⬅️ Назад",
    "btn_stop_confirm": "✅ Да, остановить",

    # --- статус
    "status_title": "📊 <b>Статус</b>",
    "status_sub_active": "💎 Подписка: <b>активна</b> ({plan})\n📅 До: <b>{until}</b>",
    "status_sub_lifetime": "💎 Подписка: <b>навсегда</b> ♾",
    "status_sub_expired": "⌛️ Подписка: <b>истекла</b> {until}",
    "status_sub_none": "⌛️ Подписка: <b>нет</b>",
    "status_conn_on": "🔗 Бизнес-подключение: <b>активно</b>",
    "status_conn_off": "🔗 Бизнес-подключение: <b>отключено</b>",
    "status_conn_none": (
        "🔗 Бизнес-подключение: <b>нет</b>\n"
        "Подключите: Настройки → Telegram для бизнеса → Чат-боты → @{bot_username}"
    ),
    "status_notif_on": "🔔 Уведомления: <b>включены</b>",
    "status_notif_off": "🔕 Уведомления: <b>на паузе</b>",

    # --- тарифы
    "plan_trial": "пробный период",
    "plan_m1": "30 дней",
    "plan_m3": "90 дней",
    "plan_y1": "1 год",
    "plan_life": "навсегда",
    "plan_grant": "выдана администратором",
    "buy_title": "💳 <b>Выберите тариф</b>\nОплата — Telegram Stars ⭐",
    "plan_button": "{name} — {stars} ⭐",
    "invoice_title": "Подписка: {name}",
    "invoice_description": "Уведомления о факте удаления сообщений в ваших бизнес-чатах. Тариф: {name}.",
    "invoice_label": "Подписка ({name})",
    "invoice_sent": "🧾 Счёт выставлен — оплатите его кнопкой ниже.",
    "payment_success": "✅ Оплата получена! Подписка активна до <b>{until}</b>.",
    "payment_success_lifetime": "✅ Оплата получена! Подписка активна <b>навсегда</b> ♾",
    "precheckout_error": "Не удалось проверить счёт. Пожалуйста, запросите новый через «💳 Купить».",
    "payment_refunded": "↩️ Возврат {amount} ⭐ выполнен. Подписка скорректирована.",

    # --- помощь
    "help": (
        "❓ <b>Помощь</b>\n\n"
        "1. Подключите бота: Настройки → Telegram для бизнеса → Чат-боты → @{bot_username}.\n"
        "2. Выберите, к каким чатам у бота будет доступ.\n"
        "3. Когда собеседник удалит сообщение, я пришлю уведомление: автор, чат, время отправки "
        "и время удаления.\n\n"
        "ℹ️ Особенности:\n"
        "• Отслеживаются только сообщения, пришедшие <b>после</b> подключения бота.\n"
        "• Telegram не сообщает, кто именно удалил сообщение, — указывается его автор.\n"
        "• Ваши собственные сообщения в уведомления не попадают.\n"
        "• Текст и метаданные хранятся не дольше {retention} дн. и стираются после уведомления.\n\n"
        "💳 Оплата и возвраты: /paysupport\n\n"
        "{privacy}"
    ),
    "paysupport": (
        "💬 <b>Поддержка по платежам</b>\n"
        "Если с оплатой что-то пошло не так или вы хотите вернуть звёзды, напишите администратору "
        "и укажите ваш ID: <code>{user_id}</code>."
    ),

    # --- стоп / возобновление
    "stop_confirm": (
        "⛔ Остановить уведомления?\n"
        "Сохранённые метаданные ваших чатов будут удалены. Подписка при этом не отменяется."
    ),
    "stopped": (
        "⛔ Уведомления остановлены, метаданные удалены ({count} зап.).\n\n"
        "Чтобы полностью отключить бота от аккаунта: Настройки → Telegram для бизнеса → "
        "Чат-боты → удалить бота."
    ),
    "resumed": "▶️ Уведомления снова включены.",

    # --- бизнес-подключение
    "connected": (
        "🔗 <b>Бот подключён к вашему аккаунту!</b>\n"
        "Теперь я сообщу, если собеседник удалит сообщение в доступных мне чатах."
    ),
    "disconnected": "🔌 Бот отключён от аккаунта. Ваши данные сохранены — при повторном подключении всё восстановится.",

    # --- уведомления об удалении
    "deleted_single": "🗑 <b>Сообщение удалено</b>\n\n{entry}",
    "deleted_multi": "🗑 <b>Удалено сообщений: {count}</b>\n\n{entries}",
    "deleted_entry": (
        "👤 Автор: {author}\n"
        "💬 Чат: {chat}\n"
        "📨 Отправлено: {sent}\n"
        "🗑 Удалено: {deleted}"
    ),
    "deleted_unknown": "🗑 Сообщение удалено (детали отправителя недоступны)\n💬 Чат: {chat}\n🗑 Удалено: {deleted}",
    "deleted_unknown_entry": "❔ Детали отправителя недоступны\n💬 Чат: {chat}\n🗑 Удалено: {deleted}",
    # Содержимое прячется под спойлер в цитате — открывается по нажатию
    # Содержимое: текст (с форматированием) под спойлером в цитате — открывается по нажатию
    "content_quote": "<blockquote><tg-spoiler>{text}</tg-spoiler></blockquote>",
    "watermark": "\n\n<a href=\"https://t.me/{bot}\">@{bot}</a>",
    # Удаление
    "del_head": "🗑 <b>{author}</b> удалил сообщение",
    "del_head_media": "📷 <b>{author}</b> удалил медиа",
    "fwd_from": "↪️ переслано от {src}",
    "del_time": "🕒 {sent} → 🗑 {deleted}",
    "deleted_unknown_compact": "🗑 Удалено сообщений: {count} (детали недоступны) · {deleted}",
    "deleted_more_compact": "… и ещё {count}",
    # Редактирование
    "edit_head": "✏️ <b>{author}</b> отредактировал сообщение",
    "edit_head_media": "✏️ <b>{author}</b> изменил подпись · {type}",
    "edit_time": "🕒 {edited}",
    "edit_new_label": "🆕 Новое:",
    "edit_old_label": "📜 Старое:",
    "edit_old_unavailable": "<i>прежняя версия недоступна</i>",
    "deleted_no_text": "📎 Вложение: {type}",
    "deleted_media_caption": "🗑 Удалённое медиа\n⤷ {author}\n⏱ {deleted}",
    "deleted_media_unavailable": "📎 Медиа ({count}) больше недоступно — Telegram не отдаёт файл.",
    "deleted_more": "…и ещё {count}",

    # --- подписка истекла
    "sub_expired_reminder": (
        "⌛️ <b>Подписка истекла.</b>\n"
        "Уведомления об удалённых сообщениях приостановлены. Продлите подписку, чтобы снова их получать."
    ),

    # --- админка
    "admin_stats": (
        "📈 <b>Статистика</b>\n"
        "👥 Пользователей: <b>{users}</b>\n"
        "💎 Активных подписок: <b>{active_subs}</b> (платных: {paid_subs})\n"
        "🔗 Активных подключений: <b>{connections}</b>\n"
        "⭐ Получено звёзд: <b>{stars}</b>\n"
        "🗂 Записей метаданных: <b>{messages_meta}</b>"
    ),
    "admin_grant_usage": "Использование: <code>/grant &lt;user_id&gt; &lt;дней|forever&gt;</code>",
    "admin_extend_usage": "Использование: <code>/extend &lt;user_id&gt; &lt;дней|forever&gt;</code>",
    "admin_revoke_usage": "Использование: <code>/revoke &lt;user_id&gt;</code>",
    "admin_revoke_ok": "⛔ Подписка пользователя <code>{user_id}</code> отозвана.",
    "admin_revoke_none": "❌ У пользователя <code>{user_id}</code> нет подписки.",
    "admin_subinfo_usage": "Использование: <code>/subinfo &lt;user_id&gt;</code>",
    "admin_subinfo_active": "💎 Активна ({plan}), до <b>{until}</b>",
    "admin_subinfo_inactive": "⌛️ Неактивна (истекла {until})",
    "admin_subinfo": (
        "👤 <b>Пользователь</b> <code>{user_id}</code>\n"
        "{sub}\n"
        "🔗 Подключений: <b>{conn_active}</b> активно из {conn_total}\n"
        "🗂 Записей метаданных: <b>{messages}</b>"
    ),
    "admin_users_empty": "Пользователей нет.",
    "admin_users_title": "👥 <b>Пользователи</b> (показано: {count})",
    "admin_backup_ok": "💾 Копия создана: <code>{path}</code> (~{size} КБ)",
    "admin_backup_file": "Резервная копия базы",
    "admin_backup_error": "❌ Не удалось создать копию: <code>{error}</code>",
    "admin_grant_ok": "✅ Пользователю <code>{user_id}</code> выдано {days} дн. Действует до <b>{until}</b>.",
    "admin_grant_notify": "🎁 Администратор выдал вам подписку на {days} дн. Действует до <b>{until}</b>.",
    "admin_refund_usage": (
        "Использование: <code>/refund &lt;telegram_payment_charge_id&gt;</code>\n"
        "Список платежей: <code>/payments [user_id]</code>"
    ),
    "admin_refund_ok": "↩️ Возврат по платежу <code>{charge_id}</code> выполнен ({amount} ⭐).",
    "admin_refund_not_found": "❌ Платёж не найден или уже возвращён.",
    "admin_refund_error": "❌ Telegram отклонил возврат: <code>{error}</code>",
    "admin_payments_empty": "Платежей нет.",
    "admin_payments_title": "🧾 <b>Последние платежи</b>",

    # --- ошибки
    # --- история и подключение
    "btn_history": "🕓 История",
    "btn_connect": "🔗 Подключить",
    "history_title": "🕓 <b>История сообщений</b>",
    "history_empty": "Пока нет сохранённых записей.\nОни появятся, когда в подключённых чатах придут сообщения.",
    "history_page_header": "Стр. {page}/{pages} · всего {total}",
    "history_filter_q": "🔎 Поиск: <code>{q}</code>",
    "btn_hist_all": "♻️ Все",
    "btn_hist_7d": "🗓 7 дн",
    "btn_hist_30d": "🗓 30 дн",
    "btn_hist_deleted": "🗑 Удалённые",
    "btn_hist_search": "🔎 Поиск",
    "history_search_prompt": "🔎 Пришлите текст для поиска по сохранённым сообщениям:",
    "history_item_gone": "Запись не найдена.",
    "history_status_deleted": "удалено",
    "history_status_active": "на месте",
    "history_item_title": "🗒 <b>Запись</b>",
    "history_item_when": "🕒 Отправлено: {when} ({status})",
    "history_item_deleted": "🗑 Удалено: {when}",
    "history_item_text": "<blockquote>{text}</blockquote>",
    "history_item_media": "📎 Вложение: {type}",
    "history_item_media_caption": "🗒 Из вашей истории",
    "history_item_media_gone": "📎 Медиа больше недоступно — Telegram не отдаёт файл.",
    "connect_guide": (
        "🔗 <b>Подключение за 3 шага</b>\n\n"
        "1. Настройки Telegram → <b>Telegram для бизнеса</b> → <b>Чат-боты</b>\n"
        "2. Вставьте бота:  <code>@{bot_username}</code>  (нажмите, чтобы скопировать)\n"
        "3. Включите доступ <b>«Управление сообщениями»</b> и сохраните\n\n"
        "Готово — бот начнёт присылать уведомления. Нужен Telegram Premium."
    ),
    "btn_connect_open": "👉 Открыть бота",
    # --- уведомления (настройки) и экспорт
    "btn_notifs": "🔔 Уведомления",
    "notif_title": "🔔 <b>Уведомления</b>\n\nВыберите, о чём присылать уведомления. Настройки сохраняются.",
    "nt_deleted": "🗑 Удаления",
    "nt_edited": "✏️ Правки",
    "nt_silent": "🔕 Тихий режим (без звука)",
    "sw_on": "✅",
    "sw_off": "❌",
    "btn_export": "📦 Экспорт данных",
    "export_building": "📦 Готовлю экспорт, секунду…",
    "export_empty": "Пока нет сохранённых сообщений для экспорта.",
    "export_caption": "📦 Ваш архив: {count} сообщ. Внутри HTML, TXT и JSON.",
    "export_error": "⚠️ Не удалось собрать экспорт. Попробуйте позже.",
    "error_generic": "⚠️ Произошла ошибка. Попробуйте ещё раз позже.",
}
