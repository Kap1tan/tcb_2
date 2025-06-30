import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, FSInputFile
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (получить у @BotFather)
BOT_TOKEN = "8045172167:AAGfNM2GOwD4H5NQp1Zkn5hwyO-QRVfcH7k"


# Состояния пользователя
class UserStates(StatesGroup):
    started = State()
    saw_welcome = State()
    saw_menu = State()
    choosing_payment = State()
    paid = State()
    accepted_rules = State()
    completed = State()


# Хранилище для отслеживания пользователей
user_data: Dict[int, dict] = {}
users_to_remind: Set[int] = set()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
scheduler = AsyncIOScheduler()


# Клавиатуры
def get_menu_keyboard():
    """Создает клавиатуру главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить доступ ✅", callback_data="pay_access")
    builder.button(text="Посмотреть отзывы 🤍", url="https://t.me/+5kCM-Acb3a00Y2Yy")
    builder.adjust(1)
    return builder.as_markup()


def get_payment_keyboard():
    """Создает клавиатуру для оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Получить доступ 🔥", callback_data="process_payment")
    return builder.as_markup()


def get_rules_keyboard():
    """Создает клавиатуру для принятия правил"""
    builder = InlineKeyboardBuilder()
    builder.button(text="ПРИНИМАЮ ПРАВИЛА ✅", callback_data="accept_rules")
    return builder.as_markup()


def get_channel_keyboard():
    """Создает клавиатуру для входа в канал и полного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Войти в канал", url="https://t.me/+vrvFmsnEsVxiNTEy")
    builder.button(text="Полное меню", callback_data="full_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_reminder_keyboard():
    """Создает клавиатуру для напоминания"""
    builder = InlineKeyboardBuilder()
    builder.button(text="ОПЛАТИТЬ ДОСТУП ✅", callback_data="pay_access")
    return builder.as_markup()


# --- Новая клавиатура для отвязки карты ---
def get_unlink_card_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отвязать карту", callback_data="unlink_card_confirm")
    return builder.as_markup()


# --- Клавиатура подтверждения отвязки ---
def get_confirm_unlink_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отвязать", callback_data="unlink_card_done")
    return builder.as_markup()


# Тексты сообщений
WELCOME_MESSAGE = """Жду тебя в моём закрытом клубе <b>«Творческий кооператив» 

Это пространство для владельцев творческих мастерских, гончарных студий и школ</b> 🌷

Внутри канала уже есть:
1. Простые и готовые решения для управления мастерской, студией, школой и внутренними процессами
2. Мощная база знаний по росту и масштабированию
3. Инструменты для продаж и позиционирования
4. Регулярные эфиры с ответами на ваши вопросы и разбором студий участников

📌 Стоимость доступа — <b>490₽ в месяц</b>

Этот канал — записки руководителя мастерских, которые существуют 9 лет
Материалы уже помогли десяткам предпринимателей стабилизировать бизнес и выйти в рост. Ты можешь посмотреть их истории, нажав на кнопку <a href="https://t.me/+5kCM-Acb3a00Y2Yy">ОТЗЫВЫ</a>

И после — присоединяйся к каналу <b>по кнопке ОПЛАТИТЬ ДОСТУП</b> ✅"""

MENU_MESSAGE = "Выбери интересующий пункт меню 🤍"

PAYMENT_MESSAGE = """<b>Стоимость подписки:</b>
· 1 месяц 490₽
· 6 месяцев 2.490₽ <s>(2.990₽)</s>
· 12 месяцев 4.490₽ <s>(5.990₽)</s>

Если у вас возникли проблемы с оплатой, то обратитесь в поддержку @tvoiportret_admin они помогут вам 🤍

<b>Получить доступ 👇</b>"""

RULES_MESSAGE = """В нашем сообществе есть правила, перед тем, как получить доступ к <b>"Творческому кооперативу"</b> ознакомься с ними:

<b>1. Уважение и доброжелательность 🤝</b>
Мы здесь ради поддержки, обмена опытом и роста. Без осуждения, негатива и "учительства сверху". Каждое мнение ценно — пусть атмосфера будет тёплой и безопасной

<b>2. Общение по делу</b>
Пишите в тему: по управлению студиями, командой, продажами, продвижением и творчеством в бизнесе. Здесь не спамят, не рекламируют без согласования и не кидают ссылки на сторонние ресурсы

<b>3. Вопросы — это норма</b>
Задавайте любые вопросы, даже если они вам кажутся "глупыми". Возможно, ваш вопрос — это чей-то ответ

<b>4. У нас нет конкуренции 🌀</b>
Мы не конкуренты. Здесь можно делиться — идеями, подходами, фишками. Вместе мы сильнее

<b>5. Участвуй, не молчи 💬</b>
Тишина не ведёт к росту. Знакомься, участвуй в эфирах, пиши, комментируй — ты здесь не просто наблюдатель, а часть кооператива

<b>6. Всё, что здесь — остаётся здесь 💌</b>
Канал закрытый. Прошу не выносить за его пределы личные истории, стратегии, материалы без согласия автора

<b>7. Если нарушаешь — сначала мягко предупредим, потом — удалим</b>"""

ACCESS_MESSAGE = "🎨 <b>Твой доступ в \"Творческий кооператив\"</b>"

REMINDER_MESSAGE = """⏳ <b>Прошел час с твоего первого шага</b>, и, возможно, тебя просто что-то отвлекло

А может, тебе важно понять, а стоит ли оно того?

<b>Вот что ты получишь внутри закрытого канала «Творческий кооператив»:</b>
🔹 Прямые эфиры с разборами студий, ответами на живые вопросы
🔹 Инструменты для продаж, допродаж и позиционирования
🔹 База знаний по управлению, команде и маркетингу
🔹 Готовые таблицы: учёт, финансы, расписание, мероприятия
🔹 Нетворкинг с такими же владельцами творческих студий, как ты

Это не мотивация на один вечер. Это опора, которую можно пересматривать, внедрять, расти и не выгорать

<b>Канал — это мой опыт.</b>
Я начинала с подвала — а теперь у меня студии в разных городах, самый красивый маркет в стране, огромный магазин и собственное производство

Если тебе важно системно расти в творческом бизнесе — жду тебя внутри

<b>Доступ — всего 490₽ в месяц</b>

👉 Нажимай «ОПЛАТИТЬ ДОСТУП»"""


# Обработчики
@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id

    # Инициализируем данные пользователя
    user_data[user_id] = {
        'start_time': datetime.now(),
        'state': 'started'
    }

    # Добавляем пользователя в список для напоминания
    users_to_remind.add(user_id)

    # Планируем напоминание через час
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=datetime.now() + timedelta(hours=1),
        args=[user_id],
        id=f"reminder_{user_id}",
        replace_existing=True
    )

    await state.set_state(UserStates.started)

    # Отправляем видео-кружок (замените путь на ваш файл)
    try:
        # Используйте file_id существующего видео или загрузите файл
        video_note = FSInputFile("video_note.mp4")  # Путь к вашему видео
        await message.answer_video_note(video_note)
    except Exception as e:
        logger.error(f"Ошибка отправки видео: {e}")
        await message.answer("🎬 Приветственное видео")

    # Отправляем приветственное сообщение через 3 секунды
    await asyncio.sleep(3)
    await message.answer(WELCOME_MESSAGE, parse_mode="HTML", disable_web_page_preview=True)
    await state.set_state(UserStates.saw_welcome)

    # Отправляем меню через 3 секунды
    await asyncio.sleep(3)
    await message.answer(MENU_MESSAGE, reply_markup=get_menu_keyboard())
    await state.set_state(UserStates.saw_menu)


@router.callback_query(F.data == "pay_access")
async def pay_access_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Оплатить доступ'"""
    user_id = callback.from_user.id

    # Убираем пользователя из списка напоминаний
    users_to_remind.discard(user_id)

    # Отменяем запланированное напоминание
    try:
        scheduler.remove_job(f"reminder_{user_id}")
    except:
        pass

    await callback.message.edit_text(
        PAYMENT_MESSAGE,
        reply_markup=get_payment_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.choosing_payment)
    await callback.answer()


@router.callback_query(F.data == "process_payment")
async def process_payment_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Получить доступ'"""
    # Здесь будет интеграция с платежной системой
    # Пока просто имитируем успешную оплату

    await callback.message.edit_text(
        RULES_MESSAGE,
        reply_markup=get_rules_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.paid)
    await callback.answer("✅ Оплата прошла успешно!")


@router.callback_query(F.data == "accept_rules")
async def accept_rules_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Принимаю правила'"""
    await callback.message.edit_text(
        ACCESS_MESSAGE,
        reply_markup=get_channel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.completed)
    await callback.answer("🎉 Добро пожаловать в сообщество!")


@router.callback_query(F.data == "full_menu")
async def full_menu_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Полное меню:",
        reply_markup=get_unlink_card_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "unlink_card_confirm")
async def unlink_card_confirm_handler(callback: CallbackQuery, state: FSMContext):
    text = (
        "\ud83d\udd10 Уверены, что хотите отвязать карту?\n\n"
        "Мы не храним данные карты - используем только защищённый токен платёжной системы.\n"
        "Он нужен только для автоматического продления подписки, без вашего участия\n\n"
        "Если вы отвяжете карту:\n"
        "— доступ к каналу останется до конца оплаченного периода\n"
        "— дальше подписка не продлится автоматически"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_confirm_unlink_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "unlink_card_done")
async def unlink_card_done_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Карта успешно отвязана", show_alert=True)
    await callback.message.edit_text("Карта успешно отвязана. Доступ к каналу сохранён до конца оплаченного периода.")


async def send_reminder(user_id: int):
    """Отправляет напоминание пользователю через час"""
    if user_id in users_to_remind:
        try:
            await bot.send_message(
                user_id,
                REMINDER_MESSAGE,
                reply_markup=get_reminder_keyboard(),
                parse_mode="HTML"
            )
            users_to_remind.discard(user_id)
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")


# Регистрация роутера
dp.include_router(router)


async def main():
    """Запуск бота"""
    # Запускаем планировщик
    scheduler.start()

    # Удаляем webhook и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())