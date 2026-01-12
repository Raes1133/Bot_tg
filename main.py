import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_TOKEN = '8550171475:AAGVRnxjB6f49XAUpuQ-2TWXuwdxN67HG0s'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('events.db', check_same_thread=False)
    cursor = conn.cursor()

    # Простая таблица без лишних полей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        event_date TEXT NOT NULL,
        notify_time TEXT DEFAULT '09:00',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    return conn


# Глобальное соединение с БД
db_connection = init_db()


class EventStates(StatesGroup):
    waiting_description = State()
    waiting_date = State()
    waiting_time = State()


# Упрощенные функции для работы с БД
def save_event_to_db(user_id, description, event_date, notify_time='09:00'):
    """Просто сохраняем событие в БД"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            'INSERT INTO events (user_id, description, event_date, notify_time) VALUES (?, ?, ?, ?)',
            (user_id, description, event_date, notify_time)
        )
        db_connection.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")
        return None


def get_all_events_from_db(user_id):
    """Получаем ВСЕ события пользователя"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            'SELECT id, description, event_date, notify_time FROM events WHERE user_id = ? ORDER BY event_date',
            (user_id,)
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения событий: {e}")
        return []


def get_event_from_db(event_id, user_id):
    """Получаем конкретное событие"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            'SELECT id, description, event_date, notify_time FROM events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка получения события: {e}")
        return None


def delete_event_from_db(event_id, user_id):
    """Удаляем событие"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            'DELETE FROM events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        db_connection.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка удаления события: {e}")
        return False


# Простые клавиатуры
def get_main_menu():
    """Главное меню"""
    buttons = [
        [KeyboardButton(text="➕ Добавить событие")],
        [KeyboardButton(text="📋 Мои события")],
        [KeyboardButton(text="🗑️ Удалить событие")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_cancel_button():
    """Кнопка отмены"""
    buttons = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_time_buttons():
    """Кнопки выбора времени"""
    builder = InlineKeyboardBuilder()

    times = [
        ("🌅 07:00", "07:00"),
        ("☀️ 09:00", "09:00"),
        ("⏰ 12:00", "12:00"),
        ("🌇 15:00", "15:00"),
        ("🌆 18:00", "18:00"),
        ("🌙 21:00", "21:00"),
    ]

    for text, time in times:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"time_{time}"))

    builder.row(InlineKeyboardButton(text="✏️ Другое время", callback_data="custom_time"))
    builder.adjust(2)
    return builder.as_markup()


def get_events_list_keyboard(events):
    """Клавиатура со списком событий"""
    builder = InlineKeyboardBuilder()

    for event in events:
        event_id, description, _, _ = event
        # Обрезаем длинное описание
        short_desc = (description[:25] + "...") if len(description) > 25 else description
        builder.add(InlineKeyboardButton(
            text=f"📅 #{event_id}: {short_desc}",
            callback_data=f"event_{event_id}"
        ))

    builder.adjust(1)
    return builder.as_markup()


def get_event_action_keyboard(event_id):
    """Клавиатура действий с событием (только удаление)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{event_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_events")
    )
    return builder.as_markup()


# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🤖 <b>Бот-напоминатель событий</b>\n\n"
        "Я буду напоминать вам о важных событиях каждый день.\n\n"
        "<b>Основные функции:</b>\n"
        "➕ Добавить событие - создать новое напоминание\n"
        "📋 Мои события - посмотреть все ваши события\n"
        "🗑️ Удалить событие - удалить ненужное событие\n\n"
        "Используйте меню ниже:",
        parse_mode='HTML',
        reply_markup=get_main_menu()
    )


@dp.message(F.text == "➕ Добавить событие")
async def start_add_event(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 <b>Введите описание события:</b>\n"
        "Например: День рождения, Встреча, Дедлайн",
        parse_mode='HTML',
        reply_markup=get_cancel_button()
    )
    await state.set_state(EventStates.waiting_description)


@dp.message(EventStates.waiting_description, F.text == "❌ Отмена")
async def cancel_adding(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Добавление отменено.", reply_markup=get_main_menu())


@dp.message(EventStates.waiting_description)
async def save_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "📅 <b>Введите дату события:</b>\n"
        "Формат: <b>ДД.ММ.ГГГГ</b>\n"
        "Пример: 25.12.2024",
        parse_mode='HTML',
        reply_markup=get_cancel_button()
    )
    await state.set_state(EventStates.waiting_date)


@dp.message(EventStates.waiting_date, F.text == "❌ Отмена")
async def cancel_date(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Добавление отменено.", reply_markup=get_main_menu())


@dp.message(EventStates.waiting_date)
async def save_date(message: types.Message, state: FSMContext):
    try:
        # Пробуем разные форматы даты
        date_text = message.text.strip()

        # Проверяем формат ДД.ММ.ГГГГ
        event_date = datetime.strptime(date_text, "%d.%m.%Y")

        # Проверяем что дата не в прошлом
        if event_date.date() < datetime.now().date():
            await message.answer("❌ Дата уже прошла! Введите будущую дату.")
            return

        # Сохраняем дату в ISO формате для БД
        await state.update_data(event_date=event_date.strftime("%Y-%m-%d"))
        await state.update_data(display_date=date_text)  # Для отображения

        await message.answer(
            f"✅ Дата: <b>{date_text}</b>\n\n"
            "⏰ <b>Выберите время для ежедневных напоминаний:</b>\n"
            "(Я буду присылать напоминание каждый день в это время)",
            parse_mode='HTML',
            reply_markup=get_time_buttons()
        )
        await state.set_state(EventStates.waiting_time)

    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат даты!</b>\n"
            "Пожалуйста, введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
            "Пример: 25.12.2024",
            parse_mode='HTML'
        )


@dp.callback_query(EventStates.waiting_time, F.data.startswith("time_"))
async def select_time(callback: types.CallbackQuery, state: FSMContext):
    notify_time = callback.data.replace("time_", "")
    await process_event_creation(callback, state, notify_time)


@dp.callback_query(EventStates.waiting_time, F.data == "custom_time")
async def custom_time_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏰ <b>Введите время в формате ЧЧ:ММ</b>\n"
        "Пример: 09:30 или 14:00",
        parse_mode='HTML'
    )
    await callback.answer()


@dp.message(EventStates.waiting_time)
async def save_custom_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=get_main_menu())
        return

    try:
        # Проверяем формат времени
        time_text = message.text.strip()
        datetime.strptime(time_text, "%H:%M")
        await process_event_creation(message, state, time_text, is_callback=False)
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n"
            "Пожалуйста, введите время в формате <b>ЧЧ:ММ</b>\n"
            "Пример: 09:30",
            parse_mode='HTML'
        )


async def process_event_creation(source, state: FSMContext, notify_time: str, is_callback=True):
    """Финальное сохранение события"""
    user_data = await state.get_data()

    # Проверяем что все данные есть
    if 'description' not in user_data or 'event_date' not in user_data:
        error_msg = "❌ Ошибка: не все данные заполнены. Попробуйте снова."
        if is_callback:
            await source.message.edit_text(error_msg)
        else:
            await source.answer(error_msg)
        await state.clear()
        return

    user_id = source.from_user.id
    description = user_data['description']
    event_date = user_data['event_date']
    display_date = user_data.get('display_date', event_date)

    # Сохраняем в БД
    event_id = save_event_to_db(user_id, description, event_date, notify_time)

    if not event_id:
        error_msg = "❌ Не удалось сохранить событие. Попробуйте снова."
        if is_callback:
            await source.message.edit_text(error_msg)
        else:
            await source.answer(error_msg)
        await state.clear()
        return

    # Рассчитываем сколько дней осталось
    try:
        event_date_obj = datetime.strptime(event_date, "%Y-%m-%d").date()
        days_left = (event_date_obj - datetime.now().date()).days
    except:
        days_left = "?"

    success_msg = (
        f"✅ <b>Событие #{event_id} успешно добавлено!</b>\n\n"
        f"📝 <b>{description}</b>\n"
        f"📅 Дата: {display_date}\n"
        f"⏰ Напоминание: каждый день в {notify_time}\n"
        f"⏳ Дней осталось: <b>{days_left}</b>"
    )

    if is_callback:
        await source.message.edit_text(success_msg, parse_mode='HTML')
    else:
        await source.answer(success_msg, parse_mode='HTML')

    # Показываем меню
    if is_callback:
        await source.message.answer("Что дальше?", reply_markup=get_main_menu())
    else:
        await source.answer("Что дальше?", reply_markup=get_main_menu())

    await state.clear()


@dp.message(F.text == "📋 Мои события")
async def show_all_events(message: types.Message):
    user_id = message.from_user.id

    # Получаем все события пользователя
    events = get_all_events_from_db(user_id)

    if not events:
        await message.answer(
            "📭 <b>У вас пока нет сохраненных событий.</b>\n"
            "Нажмите «➕ Добавить событие», чтобы создать первое!",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
        return

    # Формируем список событий
    events_text = "📋 <b>Ваши события:</b>\n\n"

    for event in events:
        event_id, description, event_date_str, notify_time = event

        # Парсим дату (поддерживаем оба формата)
        try:
            if '-' in event_date_str:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            else:
                event_date = datetime.strptime(event_date_str, "%d.%m.%Y")

            days_left = (event_date.date() - datetime.now().date()).days

            if days_left > 0:
                status = f"⏳ {days_left} дней"
            elif days_left == 0:
                status = "🎉 СЕГОДНЯ!"
            else:
                status = f"✅ Прошло {-days_left} дней"

        except:
            status = "📅 Дата не определена"

        events_text += (
            f"<b>#{event_id}</b> - {description}\n"
            f"📅 {event_date_str} | ⏰ {notify_time}\n"
            f"{status}\n"
            f"{'-' * 30}\n"
        )

    # Создаем клавиатуру
    keyboard = get_events_list_keyboard(events)

    await message.answer(
        events_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("event_"))
async def show_event_details(callback: types.CallbackQuery):
    event_id = int(callback.data.replace("event_", ""))
    user_id = callback.from_user.id

    # Получаем событие из БД
    event = get_event_from_db(event_id, user_id)

    if not event:
        await callback.message.edit_text("❌ Событие не найдено!")
        await callback.answer()
        return

    event_id, description, event_date_str, notify_time = event

    # Парсим дату
    try:
        if '-' in event_date_str:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        else:
            event_date = datetime.strptime(event_date_str, "%d.%m.%Y")

        days_left = (event_date.date() - datetime.now().date()).days

        if days_left > 0:
            status = f"⏳ Осталось дней: {days_left}"
        elif days_left == 0:
            status = "🎉 Событие сегодня!"
        else:
            status = f"✅ Прошло дней: {-days_left}"

    except:
        status = "📅 Дата не определена"

    event_info = (
        f"📋 <b>Событие #{event_id}</b>\n\n"
        f"📝 <b>{description}</b>\n"
        f"📅 Дата: {event_date_str}\n"
        f"⏰ Напоминание: {notify_time}\n"
        f"📌 {status}\n\n"
        f"Выберите действие:"
    )

    await callback.message.edit_text(
        event_info,
        parse_mode='HTML',
        reply_markup=get_event_action_keyboard(event_id)
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_events")
async def return_to_events_list(callback: types.CallbackQuery):
    # Просто вызываем функцию показа событий
    await show_all_events(callback.message)
    await callback.answer()


@dp.message(F.text == "🗑️ Удалить событие")
async def start_delete_event(message: types.Message):
    user_id = message.from_user.id
    events = get_all_events_from_db(user_id)

    if not events:
        await message.answer(
            "📭 <b>У вас нет событий для удаления.</b>",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
        return

    # Показываем список событий
    await show_all_events(message)


@dp.callback_query(F.data.startswith("delete_"))
async def confirm_delete_event(callback: types.CallbackQuery):
    event_id = int(callback.data.replace("delete_", ""))

    # Создаем клавиатуру подтверждения
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"confirm_delete_{event_id}"
        ),
        InlineKeyboardButton(
            text="❌ Нет, отмена",
            callback_data=f"event_{event_id}"
        )
    )

    await callback.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите удалить это событие?</b>\n"
        "Это действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def execute_delete_event(callback: types.CallbackQuery):
    event_id = int(callback.data.replace("confirm_delete_", ""))
    user_id = callback.from_user.id

    # Получаем информацию о событии перед удалением
    event = get_event_from_db(event_id, user_id)

    if event:
        _, description, _, _ = event
        success = delete_event_from_db(event_id, user_id)

        if success:
            await callback.message.edit_text(
                f"✅ Событие <b>#{event_id}: {description}</b> успешно удалено!",
                parse_mode='HTML'
            )

            # Возвращаемся к списку через секунду
            await asyncio.sleep(1.5)
            await show_all_events(callback.message)
        else:
            await callback.message.edit_text("❌ Не удалось удалить событие.")
    else:
        await callback.message.edit_text("❌ Событие не найдено!")

    await callback.answer()


@dp.message(F.text == "❓ Помощь")
@dp.message(Command("help"))
async def show_help(message: types.Message):
    help_text = (
        "📚 <b>Помощь по боту</b>\n\n"

        "<b>Основные команды:</b>\n"
        "➕ Добавить событие - создать новое напоминание\n"
        "📋 Мои события - посмотреть все ваши события\n"
        "🗑️ Удалить событие - удалить ненужное событие\n\n"

        "<b>Как добавить событие:</b>\n"
        "1. Нажмите «➕ Добавить событие»\n"
        "2. Введите описание события\n"
        "3. Введите дату в формате ДД.ММ.ГГГГ\n"
        "4. Выберите время для ежедневных напоминаний\n\n"

        "<b>Как посмотреть события:</b>\n"
        "1. Нажмите «📋 Мои события»\n"
        "2. Вы увидите список всех ваших событий\n"
        "3. Нажмите на событие для подробной информации\n\n"

        "<b>Как удалить событие:</b>\n"
        "1. Нажмите «🗑️ Удалить событие» или выберите событие из списка\n"
        "2. Нажмите «🗑️ Удалить»\n"
        "3. Подтвердите удаление\n\n"

        "<b>Особенности:</b>\n"
        "• Напоминания приходят ежедневно в выбранное время\n"
        "• Данные сохраняются при перезапуске бота\n"
        "• Можно создать неограниченное количество событий\n\n"

        "<b>Поддержка:</b>\n"
        "Если возникли проблемы, перезапустите бота командой /start"
    )

    await message.answer(help_text, parse_mode='HTML', reply_markup=get_main_menu())


# Ежедневные напоминания
async def send_daily_reminders():
    """Отправка ежедневных напоминаний"""
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")

            # Получаем все события для текущего времени
            cursor = db_connection.cursor()
            cursor.execute(
                'SELECT user_id, id, description, event_date FROM events WHERE notify_time = ?',
                (current_time,)
            )

            events = cursor.fetchall()

            if events:
                logger.info(f"Отправка напоминаний в {current_time}: {len(events)} событий")

                for user_id, event_id, description, event_date_str in events:
                    try:
                        # Парсим дату
                        try:
                            if '-' in event_date_str:
                                event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
                            else:
                                event_date = datetime.strptime(event_date_str, "%d.%m.%Y")

                            days_left = (event_date.date() - now.date()).days

                            if days_left > 0:
                                message = (
                                    f"⏰ <b>Ежедневное напоминание!</b>\n\n"
                                    f"📝 Событие: <b>{description}</b>\n"
                                    f"📅 Дата: {event_date.strftime('%d.%m.%Y')}\n"
                                    f"⏳ Осталось дней: <b>{days_left}</b>"
                                )
                                await bot.send_message(user_id, message, parse_mode='HTML')
                            elif days_left == 0:
                                message = (
                                    f"🎉 <b>СЕГОДНЯ НАСТУПАЕТ СОБЫТИЕ!</b>\n\n"
                                    f"📝 <b>{description}</b>\n\n"
                                    "Поздравляем! 🎊"
                                )
                                await bot.send_message(user_id, message, parse_mode='HTML')

                        except Exception as e:
                            logger.error(f"Ошибка парсинга даты: {e}")
                            # Отправляем простое напоминание
                            message = f"⏰ Напоминание: {description}"
                            await bot.send_message(user_id, message)

                    except Exception as e:
                        logger.error(f"Ошибка отправки пользователю {user_id}: {e}")

            # Ждем 60 секунд перед следующей проверкой
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Ошибка в send_daily_reminders: {e}")
            await asyncio.sleep(60)


@dp.message(Command("debug"))
async def debug_info(message: types.Message):
    """Отладочная информация"""
    user_id = message.from_user.id

    # Получаем все события пользователя
    events = get_all_events_from_db(user_id)

    # Считаем события в базе
    cursor = db_connection.cursor()
    cursor.execute('SELECT COUNT(*) FROM events')
    total_events = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM events WHERE user_id = ?', (user_id,))
    user_events_count = cursor.fetchone()[0]

    debug_text = (
        f"🔍 <b>Отладочная информация</b>\n\n"
        f"👤 Ваш ID: <code>{user_id}</code>\n"
        f"📊 Всего событий в базе: {total_events}\n"
        f"📋 Ваших событий: {user_events_count}\n\n"
    )

    if events:
        debug_text += "<b>Ваши события:</b>\n"
        for i, event in enumerate(events, 1):
            event_id, description, date_str, time_str = event
            debug_text += f"{i}. #{event_id}: '{description}' - {date_str} в {time_str}\n"
    else:
        debug_text += "📭 У вас нет событий в базе\n"

    debug_text += f"\n🕐 Текущее время: {datetime.now().strftime('%H:%M:%S')}"

    await message.answer(debug_text, parse_mode='HTML')


async def main():
    logger.info("🚀 Запуск бота...")

    try:
        # Проверяем соединение с ботом
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот @{bot_info.username} готов к работе")

        # Проверяем базу данных
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        logger.info(f"📊 В базе данных {count} событий")

        # Запускаем фоновую задачу с напоминаниями
        asyncio.create_task(send_daily_reminders())

        # Запускаем бота
        await dp.start_polling(bot, skip_updates=True)

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        logger.info("⚠️ Проверьте токен бота и интернет-соединение")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    finally:
        # Закрываем соединение с БД
        if db_connection:
            db_connection.close()
            logger.info("🔒 Соединение с базой данных закрыто")