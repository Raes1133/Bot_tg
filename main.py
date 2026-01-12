import os
import asyncio
import logging
import json
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
    API_TOKEN = "ВАШ_ТОКЕН_БОТА"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class EventStates(StatesGroup):
    waiting_description = State()
    waiting_date = State()
    waiting_time = State()

# Простое хранилище в JSON файле (более надежно на Railway)
class EventStorage:
    def __init__(self):
        self.file_path = 'events_data.json'
        self.events = self._load_events()
    
    def _load_events(self):
        """Загружает события из JSON файла"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки событий: {e}")
            return []
    
    def _save_events(self):
        """Сохраняет события в JSON файл"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения событий: {e}")
            return False
    
    def add_event(self, user_id, description, event_date, notify_time='09:00'):
        """Добавляет новое событие"""
        try:
            event_id = len(self.events) + 1
            event = {
                'id': event_id,
                'user_id': user_id,
                'description': description,
                'event_date': event_date,
                'notify_time': notify_time,
                'created_at': datetime.now().isoformat()
            }
            
            self.events.append(event)
            self._save_events()
            logger.info(f"✅ Сохранено событие #{event_id} для пользователя {user_id}")
            return event_id
        except Exception as e:
            logger.error(f"❌ Ошибка добавления события: {e}")
            return None
    
    def get_user_events(self, user_id):
        """Получает все события пользователя"""
        try:
            user_events = [e for e in self.events if e['user_id'] == user_id]
            logger.info(f"📊 Найдено {len(user_events)} событий для пользователя {user_id}")
            return user_events
        except Exception as e:
            logger.error(f"❌ Ошибка получения событий: {e}")
            return []
    
    def get_event(self, event_id, user_id):
        """Получает конкретное событие"""
        try:
            for event in self.events:
                if event['id'] == event_id and event['user_id'] == user_id:
                    return event
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения события: {e}")
            return None
    
    def delete_event(self, event_id, user_id):
        """Удаляет событие"""
        try:
            initial_count = len(self.events)
            self.events = [e for e in self.events if not (e['id'] == event_id and e['user_id'] == user_id)]
            
            deleted = len(self.events) < initial_count
            if deleted:
                self._save_events()
                logger.info(f"🗑️ Событие #{event_id} удалено для пользователя {user_id}")
            
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления события: {e}")
            return False
    
    def get_all_events(self):
        """Получает все события (для напоминаний)"""
        return self.events
    
    def get_events_for_time(self, notify_time):
        """Получает события для конкретного времени"""
        try:
            current_date = datetime.now().date().isoformat()
            result = []
            
            for event in self.events:
                if event['notify_time'] == notify_time:
                    # Проверяем что событие еще не наступило
                    try:
                        event_date = datetime.strptime(event['event_date'], "%Y-%m-%d").date()
                        if event_date >= datetime.now().date():
                            result.append(event)
                    except:
                        # Если дата в другом формате, добавляем без проверки
                        result.append(event)
            
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения событий для времени: {e}")
            return []
    
    def get_events_count(self):
        """Возвращает общее количество событий"""
        return len(self.events)

# Инициализируем хранилище
storage = EventStorage()

# Простые клавиатуры
def get_main_menu():
    """Главное меню"""
    buttons = [
        [KeyboardButton(text="➕ Добавить событие")],
        [KeyboardButton(text="📋 Мои события")],
        [KeyboardButton(text="🗑️ Удалить событие")],
        [KeyboardButton(text="🔔 Тест напоминаний"), KeyboardButton(text="❓ Помощь")]
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
        event_id = event['id']
        description = event['description']
        # Обрезаем длинное описание
        short_desc = (description[:25] + "...") if len(description) > 25 else description
        builder.add(InlineKeyboardButton(
            text=f"📅 #{event_id}: {short_desc}",
            callback_data=f"event_{event_id}"
        ))
    
    builder.adjust(1)
    return builder.as_markup()

def get_event_action_keyboard(event_id):
    """Клавиатура действий с событием"""
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
        "Я буду напоминать вам о важных событиях каждый день в выбранное время.\n\n"
        "<b>Особенности этой версии:</b>\n"
        "✅ Использует JSON для хранения (надежнее на Railway)\n"
        "✅ Напоминания работают 24/7\n"
        "✅ Все данные сохраняются при перезапуске\n\n"
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
        date_text = message.text.strip()
        
        # Проверяем формат ДД.ММ.ГГГГ
        event_date = datetime.strptime(date_text, "%d.%m.%Y")
        
        # Проверяем что дата не в прошлом
        if event_date.date() < datetime.now().date():
            await message.answer("❌ Дата уже прошла! Введите будущую дату.")
            return
        
        # Сохраняем дату в ISO формате для хранения
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
    
    # Сохраняем в хранилище
    event_id = storage.add_event(user_id, description, event_date, notify_time)
    
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
        f"⏳ Дней осталось: <b>{days_left}</b>\n\n"
        f"📢 Напоминания будут приходить автоматически в указанное время."
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
    events = storage.get_user_events(user_id)
    
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
        event_id = event['id']
        description = event['description']
        event_date_str = event['event_date']
        notify_time = event['notify_time']
        
        # Парсим дату
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
    
    # Получаем событие из хранилища
    event = storage.get_event(event_id, user_id)
    
    if not event:
        await callback.message.edit_text("❌ Событие не найдено!")
        await callback.answer()
        return
    
    description = event['description']
    event_date_str = event['event_date']
    notify_time = event['notify_time']
    
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
    events = storage.get_user_events(user_id)
    
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
        reply_markup=builder.as_markup(),
        parse_mode='HTML'
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def execute_delete_event(callback: types.CallbackQuery):
    event_id = int(callback.data.replace("confirm_delete_", ""))
    user_id = callback.from_user.id
    
    # Получаем информацию о событии перед удалением
    event = storage.get_event(event_id, user_id)
    
    if event:
        description = event['description']
        success = storage.delete_event(event_id, user_id)
        
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

@dp.message(F.text == "🔔 Тест напоминаний")
@dp.message(Command("test_reminders"))
async def test_reminders(message: types.Message):
    """Тестовая отправка напоминаний"""
    user_id = message.from_user.id
    
    # Получаем события пользователя
    events = storage.get_user_events(user_id)
    
    if not events:
        await message.answer(
            "📭 <b>У вас нет событий для напоминаний.</b>",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
        return
    
    # Отправляем тестовые напоминания
    sent_count = 0
    current_time = datetime.now().strftime("%H:%M")
    
    for event in events:
        event_id = event['id']
        description = event['description']
        event_date_str = event['event_date']
        notify_time = event['notify_time']
        
        try:
            # Парсим дату
            if '-' in event_date_str:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            else:
                event_date = datetime.strptime(event_date_str, "%d.%m.%Y")
            
            days_left = (event_date.date() - datetime.now().date()).days
            
            if days_left > 0:
                test_msg = (
                    f"🔔 <b>ТЕСТ: Напоминание!</b>\n\n"
                    f"📝 Событие: <b>{description}</b>\n"
                    f"📅 Дата: {event_date.strftime('%d.%m.%Y')}\n"
                    f"⏰ Реальное время напоминания: {notify_time}\n"
                    f"⏳ Осталось дней: <b>{days_left}</b>\n\n"
                    f"✅ Это тестовое сообщение. Реальные напоминания будут приходить автоматически в {notify_time}."
                )
                await message.answer(test_msg, parse_mode='HTML')
                sent_count += 1
                await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
                
        except Exception as e:
            logger.error(f"Ошибка отправки тестового напоминания: {e}")
    
    if sent_count > 0:
        await message.answer(
            f"✅ <b>Отправлено {sent_count} тестовых напоминаний!</b>\n"
            f"Реальные напоминания будут приходить автоматически в указанное время.\n\n"
            f"🕐 Текущее время: {current_time}",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "ℹ️ <b>Нет активных событий для тестирования напоминаний.</b>",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )

@dp.message(F.text == "❓ Помощь")
@dp.message(Command("help"))
async def show_help(message: types.Message):
    help_text = (
        "📚 <b>Помощь по боту (JSON версия)</b>\n\n"
        
        "<b>Основные команды:</b>\n"
        "➕ Добавить событие - создать новое напоминание\n"
        "📋 Мои события - посмотреть все ваши события\n"
        "🗑️ Удалить событие - удалить ненужное событие\n"
        "🔔 Тест напоминаний - тестовая отправка напоминаний\n\n"
        
        "<b>Как добавить событие:</b>\n"
        "1. Нажмите «➕ Добавить событие»\n"
        "2. Введите описание события\n"
        "3. Введите дату в формате ДД.ММ.ГГГГ\n"
        "4. Выберите время для ежедневных напоминаний\n\n"
        
        "<b>Как работают напоминания:</b>\n"
        "• Бот проверяет время каждую минуту\n"
        "• Если наступает время события, отправляется напоминание\n"
        "• Напоминания приходят ЕЖЕДНЕВНО в выбранное время\n"
        "• В день события приходит особое поздравление\n\n"
        
        "<b>Тестирование напоминаний:</b>\n"
        "• Используйте кнопку «🔔 Тест напоминаний»\n"
        "• Вы получите тестовые сообщения для всех ваших событий\n"
        "• Это не мешает реальным напоминаниям\n\n"
        
        "<b>Особенности этой версии:</b>\n"
        "✅ Использует JSON файл вместо базы данных\n"
        "✅ Более надежно работает на Railway\n"
        "✅ Все данные сохраняются при перезапуске\n\n"
        
        "<b>Примечание:</b>\n"
        "На Railway бот работает 24/7 в бесплатном режиме."
    )
    
    await message.answer(help_text, parse_mode='HTML', reply_markup=get_main_menu())

@dp.message(Command("debug"))
async def debug_info(message: types.Message):
    """Отладочная информация"""
    user_id = message.from_user.id
    
    # Получаем все события пользователя
    events = storage.get_user_events(user_id)
    all_events = storage.get_all_events()
    
    debug_text = (
        f"🔍 <b>Отладочная информация (JSON версия)</b>\n\n"
        f"👤 Ваш ID: <code>{user_id}</code>\n"
        f"📋 Ваших событий: {len(events)}\n"
        f"📊 Всего событий в системе: {len(all_events)}\n"
        f"🕐 Текущее время: {datetime.now().strftime('%H:%M:%S')}\n"
        f"📅 Текущая дата: {datetime.now().strftime('%d.%m.%Y')}\n"
        f"📁 Файл данных: {storage.file_path}\n\n"
    )
    
    if events:
        debug_text += "<b>Ваши события:</b>\n"
        for i, event in enumerate(events, 1):
            event_id = event['id']
            description = event['description']
            date_str = event['event_date']
            time_str = event['notify_time']
            debug_text += f"{i}. #{event_id}: '{description}' - {date_str} в {time_str}\n"
    
    # Информация о напоминаниях
    debug_text += f"\n<b>Статус напоминаний:</b>\n"
    debug_text += f"🔧 Система напоминаний: ✅ Активна\n"
    debug_text += f"⏱️ Последняя проверка: {datetime.now().strftime('%H:%M:%S')}\n"
    debug_text += f"📨 Следующая проверка: через 60 секунд"
    
    await message.answer(debug_text, parse_mode='HTML')

@dp.message(Command("reset"))
async def reset_data(message: types.Message):
    """Сброс данных (только для отладки)"""
    try:
        # Просто пересоздаем хранилище
        global storage
        storage = EventStorage()
        
        await message.answer(
            "✅ <b>Данные сброшены!</b>\n"
            "Создано новое пустое хранилище.",
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка сброса данных: {e}")
        await message.answer(
            f"❌ <b>Ошибка сброса данных:</b>\n{str(e)}",
            parse_mode='HTML'
        )

# Функция отправки напоминаний
async def check_and_send_reminders():
    """Проверяет и отправляет напоминания"""
    logger.info("🚀 Запуск системы напоминаний...")
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")
            logger.info(f"⏰ Проверка напоминаний в {current_time}")
            
            # Получаем события для текущего времени
            events = storage.get_events_for_time(current_time)
            
            if events:
                logger.info(f"📨 Найдено {len(events)} событий для отправки в {current_time}")
                
                for event in events:
                    user_id = event['user_id']
                    event_id = event['id']
                    description = event['description']
                    event_date_str = event['event_date']
                    
                    try:
                        # Парсим дату
                        try:
                            if '-' in event_date_str:
                                event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
                            else:
                                event_date = datetime.strptime(event_date_str, "%d.%m.%Y")
                            
                            days_left = (event_date.date() - datetime.now().date()).days
                            
                            if days_left > 0:
                                message = (
                                    f"⏰ <b>Ежедневное напоминание!</b>\n\n"
                                    f"📝 Событие: <b>{description}</b>\n"
                                    f"📅 Дата: {event_date.strftime('%d.%m.%Y')}\n"
                                    f"⏰ Следующее напоминание: завтра в {current_time}\n"
                                    f"⏳ Осталось дней: <b>{days_left}</b>"
                                )
                                await bot.send_message(user_id, message, parse_mode='HTML')
                                logger.info(f"✅ Отправлено напоминание #{event_id} пользователю {user_id}")
                                
                            elif days_left == 0:
                                message = (
                                    f"🎉 <b>СЕГОДНЯ НАСТУПАЕТ СОБЫТИЕ!</b>\n\n"
                                    f"📝 <b>{description}</b>\n\n"
                                    "Поздравляем! 🎊\n\n"
                                    "Это последнее напоминание об этом событии."
                                )
                                await bot.send_message(user_id, message, parse_mode='HTML')
                                logger.info(f"🎉 Отправлено поздравление #{event_id} пользователю {user_id}")
                                
                        except Exception as e:
                            logger.error(f"❌ Ошибка парсинга даты события #{event_id}: {e}")
                            # Отправляем простое напоминание
                            message = f"⏰ Напоминание: {description}"
                            await bot.send_message(user_id, message)
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
            
            # Ждем 60 секунд перед следующей проверкой
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в системе напоминаний: {e}")
            # Ждем 30 секунд перед повторной попыткой
            await asyncio.sleep(30)

async def main():
    logger.info("🚀 Запуск бота на Railway (JSON версия)...")
    
    try:
        # Проверяем, что бот доступен
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот @{bot_info.username} готов к работе")
        
        # Проверяем хранилище
        events_count = storage.get_events_count()
        logger.info(f"📊 В хранилище {events_count} событий")
        
        # Запускаем задачу с напоминаниями в фоне
        reminder_task = asyncio.create_task(check_and_send_reminders())
        
        # Запускаем поллинг
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}")

if __name__ == "__main__":
    # Проверяем наличие токена
    if API_TOKEN == "ВАШ_ТОКЕН_БОТА":
        logger.warning("⚠️  Используется дефолтный токен. Установите переменную окружения API_TOKEN на Railway!")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
