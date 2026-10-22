"""XAMIDOV GIFT — botni ishga tushirish nuqtasi.

Ishga tushirish (lokal):
    python bot.py

Render uchun:
    MODE=worker  → faqat polling (Background Worker, 24/7)
    MODE=web     → polling + health server (Web Service; PORT orqali)
"""

from __future__ import annotations

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_IDS, BOT_TOKEN, validate_config
from database import db
from handlers import admin, gifts, orders, payments, premium, profile, promo, referrals, start, stars
from utils.logger import get_logger, setup_logging

log = get_logger("bot")

# Routerlar tartibi muhim: admin → bo'limlar → start (catch-all oxirda)
SECTION_ROUTERS = (
    admin.router,
    stars.router,
    premium.router,
    gifts.router,
    profile.router,
    payments.router,
    orders.router,
    promo.router,
    referrals.router,
    start.router,
)


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    for router in SECTION_ROUTERS:
        dispatcher.include_router(router)
    return dispatcher


async def start_health_server(port: int):
    """Web rejim uchun kichik health server (Render/UptimeRobot ping uchun)."""
    from aiohttp import web

    async def health(_request) -> web.Response:
        return web.Response(text="XAMIDOV GIFT OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Web rejim: health server http://0.0.0.0:%s/health", port)
    return runner


async def main() -> None:
    setup_logging()

    fatal, warnings = validate_config()
    for message in warnings:
        log.warning(message)
    if fatal:
        for message in fatal:
            print("\n❌ Sozlama xatosi:\n" + message)
        print("\n.env (yoki Render Environment Variables) ni to'g'rilang va qayta ishga tushiring.")
        sys.exit(1)

    mode = os.getenv("MODE", "worker").strip().lower()

    bot = Bot(BOT_TOKEN)
    dispatcher = build_dispatcher()

    await db.connect()
    try:
        me = await bot.get_me()
        log.info(
            "Bot ishga tushdi: @%s (rejim=%s, adminlar: %s)",
            me.username,
            mode,
            ", ".join(map(str, sorted(ADMIN_IDS))),
        )
        if mode == "web":
            port = int(os.getenv("PORT", "10000"))
            await start_health_server(port)

        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await db.close()
        log.info("Bot to'xtadi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot to'xtatildi.")
