import os
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения Railway
API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    logger.error("API_TOKEN не установлен! Проверьте переменные окружения в Railway.")
    # Для локального тестирования можно использовать дефолтный токен
    API_TOKEN = "8550171475:AAGVRnxjB6f49XAUpuQ-2TWXuwdxN67HG0s"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class EventStates(StatesGroup):
    waiting_description = State()
    waiting_date = State()
    waiting_time = State()

# Функции для работы с БД с исправлением ошибок
def get_db_connection():
    """Создает новое соединение с БД при каждом запросе"""
    try:
        # На Railway используем абсолютный путь
        db_path = os.path.join(os.getcwd(), 'events.db')
        logger.info(f"Подключение к базе: {db_path}")
        
        # Создаем соединение
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        
        # Включаем поддержку внешних ключей
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        # Пробуем создать новую базу
        return create_new_database()

def create_new_database():
    """Создает новую базу данных"""
    try:
        db_path = os.path.join(os.getcwd(), 'events.db')
        
        # Удаляем поврежденную базу если существует
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                logger.warning("Удалена поврежденная база данных")
            except:
                pass
        
        # Создаем новое соединение
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        
        # Создаем таблицу
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
        logger.info("Создана новая база данных")
        return conn
        
    except Exception as e:
        logger.error(f"Не удалось создать базу данных: {e}")
        raise

def init_database():
    """Инициализация базы данных с проверкой целостности"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем целостность базы данных
        cursor.execute("PRAGMA integrity_check")
        integrity_check = cursor.fetchone()[0]
        
        if integrity_check != "ok":
            logger.error(f"База повреждена: {integrity_check}")
            conn.close()
            return create_new_database()
        
        # Проверяем структуру таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        if not cursor.fetchone():
            logger.warning("Таблица events не найдена, создаем...")
            cursor.execute('''
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                event_date TEXT NOT NULL,
                notify_time TEXT DEFAULT '09:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            conn.commit()
        
        logger.info("База данных инициализирована успешно")
        return conn
        
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return create_new_database()

# Инициализируем базу данных при запуске
db_connection = init_database()

def save_event(user_id, description, event_date, notify_time='09:00'):
    """Сохраняем событие в БД"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO events (user_id, description, event_date, notify_time) VALUES (?, ?, ?, ?)',
            (user_id, description, event_date, notify_time)
        )
        conn.commit()
        event_id = cursor.lastrowid
        logger.info(f"Сохранено событие #{event_id} для пользователя {user_id}")
        
        cursor.close()
        conn.close()
        return event_id
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        if conn:
            conn.close()
        return None

def get_user_events(user_id):
    """Получаем все события пользователя"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id, description, event_date, notify_time FROM events WHERE user_id = ? ORDER BY event_date',
            (user_id,)
        )
        events = cursor.fetchall()
        logger.info(f"Найдено {len(events)} событий для пользователя {user_id}")
        
        cursor.close()
        conn.close()
        return events
    except Exception as e:
        logger.error(f"Ошибка получения событий: {e}")
        if conn:
            conn.close()
        return []

def get_event(event_id, user_id):
    """Получаем конкретное событие"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id, description, event_date, notify_time FROM events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        event = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return event
    except Exception as e:
        logger.error(f"Ошибка получения события: {e}")
        if conn:
            conn.close()
        return None

def delete_event(event_id, user_id):
    """Удаляем событие"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        
        cursor.close()
        conn.close()
        return deleted
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        if conn:
            conn.close()
        return False

# Простые клавиатуры
def get_main_menu():
    """Главное меню"""
    buttons = [
        [KeyboardButton(text="➕ Добавить событие")],
        [KeyboardButton(text="📋 Мои события")],
        [KeyboardButton(text="🗑️ Удалить событие")],
        [KeyboardButton(text="🔄 Пересоздать БД"), KeyboardButton(text="❓ Помощь")]
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
        "🗑️ Удалить событие - удалить ненужное событие\n"
        "🔄 Пересоздать БД - если есть проблемы с базой данных\n\n"
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
    event_id = save_event(user_id, description, event_date, notify_time)
    
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
    events = get_user_events(user_id)
    
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
    event = get_event(event_id, user_id)
    
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
    events = get_user_events(user_id)
    
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
    event = get_event(event_id, user_id)
    
    if event:
        _, description, _, _ = event
        success = delete_event(event_id, user_id)
        
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

@dp.message(F.text == "🔄 Пересоздать БД")
@dp.message(Command("resetdb"))
async def reset_database(message: types.Message):
    """Команда для пересоздания базы данных"""
    try:
        global db_connection
        
        # Закрываем текущее соединение
        if db_connection:
            db_connection.close()
        
        # Пересоздаем базу
        db_connection = create_new_database()
        
        await message.answer(
            "✅ <b>База данных успешно пересоздана!</b>\n"
            "Все данные были удалены. Теперь вы можете добавить новые события.",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при пересоздании БД: {e}")
        await message.answer(
            f"❌ <b>Ошибка при пересоздании БД:</b>\n{str(e)}",
            parse_mode='HTML'
        )

@dp.message(F.text == "❓ Помощь")
@dp.message(Command("help"))
async def show_help(message: types.Message):
    help_text = (
        "📚 <b>Помощь по боту</b>\n\n"
        
        "<b>Основные команды:</b>\n"
        "➕ Добавить событие - создать новое напоминание\n"
        "📋 Мои события - посмотреть все ваши события\n"
        "🗑️ Удалить событие - удалить ненужное событие\n"
        "🔄 Пересоздать БД - если есть проблемы с базой данных\n\n"
        
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
        
        "<b>Если бот не работает:</b>\n"
        "1. Попробуйте команду /start\n"
        "2. Используйте «🔄 Пересоздать БД» если есть ошибки с базой данных\n"
        "3. Перезапустите бота на Railway\n\n"
        
        "<b>Поддержка:</b>\n"
        "Если проблемы остаются, свяжитесь с разработчиком."
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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id, id, description, event_date FROM events WHERE notify_time = ?',
                (current_time,)
            )
            
            events = cursor.fetchall()
            cursor.close()
            conn.close()
            
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
    events = get_user_events(user_id)
    
    # Считаем события в базе
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM events')
    total_events = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM events WHERE user_id = ?', (user_id,))
    user_events_count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
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
    logger.info("🚀 Запуск бота на Railway...")
    
    try:
        # Проверяем, что бот доступен
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот @{bot_info.username} запущен")
        
        # Проверяем базу данных
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"📊 В базе данных {count} событий")
        
        # Запускаем фоновую задачу с напоминаниями
        asyncio.create_task(send_daily_reminders())
        
        # Запускаем поллинг
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

if __name__ == "__main__":
    # Проверяем наличие токена
    if API_TOKEN == "ВАШ_ТОКЕН_БОТА":
        logger.warning("⚠️  Используется дефолтный токен. Установите переменную окружения API_TOKEN на Railway!")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
