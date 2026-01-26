"""Telegram message handlers."""
from aiogram import Router

from word_learn.handlers.start import router as start_router
from word_learn.handlers.add_word import router as add_word_router
from word_learn.handlers.add_words import router as add_words_router
from word_learn.handlers.practice import router as practice_router
from word_learn.handlers.remind import router as remind_router
from word_learn.handlers.reset import router as reset_router


def setup_routers() -> Router:
    """Set up and return main router with all handlers."""
    main_router = Router()

    main_router.include_router(start_router)
    main_router.include_router(add_word_router)
    main_router.include_router(add_words_router)
    main_router.include_router(practice_router)
    main_router.include_router(remind_router)
    main_router.include_router(reset_router)

    return main_router
