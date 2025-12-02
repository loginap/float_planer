import json
import time
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackContext
)
from telegram.error import TelegramError, TimedOut
from float_plan import Note, create_plan, rec_note
from moods import mood_to_tags
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Получаем токен из переменной окружения
TOKEN = os.getenv('BOT_TOKEN')

# Проверяем, что токен загрузился (опционально, но рекомендуется)
if not TOKEN:
    print("Ошибка: BOT_TOKEN не найден в .env файле!")
    exit(1)


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

#TOKEN = ""

# Состояния для ConversationHandler
(ADD_NAME, ADD_DESC, ADD_PRIOR, ADD_TAGS, ADD_LEN, ADD_DATE) = range(6)
(REC_MOOD, REC_TIME, PLAN_TIME, PLAN_MOOD) = range(6, 10)


def get_user_notes_file(user_id):
    return f"notes_{user_id}.json"


async def safe_send_message(update: Update, text: str, max_retries: int = 3):
    """Безопасная отправка сообщения с повторными попытками"""
    for attempt in range(max_retries):
        try:
            if len(text) > 4096:
                parts = [text[i:i + 4096] for i in range(0, len(text), 4096)]
                for part in parts:
                    await update.message.reply_text(part)
                    time.sleep(0.5)
            else:
                await update.message.reply_text(text)
            return True
        except TimedOut:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                logger.error(f"Не удалось отправить сообщение после {max_retries} попыток")
                return False
        except TelegramError as e:
            logger.error(f"Ошибка Telegram при отправке сообщения: {e}")
            return False
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    await safe_send_message(update, "Привет! Введите /help, чтобы увидеть список команд.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Команды:
/add_note — Создать заметку
/list — Показать все заметки
/note <название> — Показать полное описание заметки
/delete <название> — Удалить заметку
/plan — Режим создания плана
/recommend — Рекомендация дел
"""
    await safe_send_message(update, help_text)


def note_to_json(note: Note, delete_mode=False, user_id=None):
    if user_id is None:
        user_id = "default"

    user_file = get_user_notes_file(user_id)

    try:
        with open(user_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except:
        data = []

    if delete_mode:
        data = [n for n in data if n["name"] != note.name]
    else:
        data.append(note.__dict__)

    with open(user_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def json_to_notes(user_id=None):
    if user_id is None:
        user_id = "default"

    user_file = get_user_notes_file(user_id)

    try:
        with open(user_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except:
        return []

    notes = []
    for note_data in data:
        try:
            len_note = note_data.get("len_note")
            if len_note is None:
                len_note = 0

            note = Note(
                note_data["name"],
                note_data["desc"],
                note_data["prior"],
                note_data["tags"],
                len_note,
                note_data.get("date", "")
            )
            notes.append(note)
        except KeyError as e:
            logger.error(f"Ошибка при загрузке заметки: {e}")
            continue
    return notes


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = json_to_notes(user_id)
    if not notes:
        await safe_send_message(update, "Заметки отсутствуют.")
        return
    msg = "\n".join([f"- {n.name}" for n in notes])
    await safe_send_message(update, "Ваши заметки:\n" + msg)


async def show_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        name = " ".join(context.args)
        if not name:
            await safe_send_message(update, "Укажите название заметки: /note <название>")
            return

        note = next(n for n in json_to_notes(user_id) if n.name == name)
        msg = f"Название: {note.name}\nОписание: {note.desc}\nПриоритет: {note.prior}\nТеги: {', '.join(note.tags)}\nВремя (мин): {note.len_note}\nДедлайн: {note.date}"
    except StopIteration:
        msg = "Заметка не найдена."
    except Exception as e:
        msg = f"Ошибка: {e}"
    await safe_send_message(update, msg)


async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        name = " ".join(context.args)
        if not name:
            await safe_send_message(update, "Укажите название заметки: /delete <название>")
            return

        note = next(n for n in json_to_notes(user_id) if n.name == name)
        note_to_json(note, delete_mode=True, user_id=user_id)
        msg = "Заметка удалена."
    except StopIteration:
        msg = "Заметка не найдена."
    except Exception as e:
        msg = f"Ошибка: {e}"
    await safe_send_message(update, msg)


# --- Создание заметки (пошагово) ---
async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update, "Введите название заметки:")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text or "Пустая заметка"
    await safe_send_message(update, "Введите описание:")
    return ADD_DESC


async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = update.message.text
    await safe_send_message(update, "Введите приоритет (1-10):")
    return ADD_PRIOR


async def add_prior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prior = int(update.message.text)
        if prior < 1 or prior > 10:
            prior = 5
        context.user_data["prior"] = prior
    except:
        context.user_data["prior"] = 5

    # Правильно собираем все уникальные теги из настроений
    all_tags_set = set()
    for mood in mood_to_tags.values():
        for tag_info in mood:
            all_tags_set.add(tag_info["tag"])

    # Преобразуем в список и сортируем для удобства
    all_tags = sorted(list(all_tags_set))
    context.user_data["all_tags"] = all_tags

    # Создаем сообщение с тегами
    tag_text = f"Доступно тегов: {len(all_tags)}\nВыберите номера тегов (через запятую):\n"
    tag_text += "\n".join([f"{i + 1}. {tag}" for i, tag in enumerate(all_tags)])

    await safe_send_message(update, tag_text)
    return ADD_TAGS


async def add_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        indices = [int(i.strip()) - 1 for i in update.message.text.split(",")]
        valid_indices = [i for i in indices if 0 <= i < len(context.user_data["all_tags"])]
        context.user_data["tags"] = [context.user_data["all_tags"][i] for i in valid_indices]
    except:
        context.user_data["tags"] = []
    await safe_send_message(update, "Введите длительность в минутах (0 если не важно):")
    return ADD_LEN


async def add_len(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        length = int(update.message.text)
        if length < 0:
            length = 0
        context.user_data["len_note"] = length
    except:
        context.user_data["len_note"] = 0
    await safe_send_message(update, "Введите дедлайн (ДД:ММ:ГГГГ или '-' если нет):")
    return ADD_DATE


async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    date = update.message.text
    context.user_data["date"] = date
    note = Note(
        context.user_data["name"],
        context.user_data["desc"],
        context.user_data["prior"],
        context.user_data["tags"],
        context.user_data["len_note"],
        context.user_data["date"]
    )
    note_to_json(note, user_id=user_id)
    await safe_send_message(update, "Заметка сохранена!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update, "Отменено.")
    return ConversationHandler.END


# --- Исправленные функции планирования ---
def safe_create_plan(notes, free_time, mood=""):
    """Безопасная версия create_plan с обработкой всех ошибок"""
    # Фильтруем заметки с указанным временем > 0
    valid_notes = [note for note in notes if note.len_note is not None and note.len_note > 0]

    if not valid_notes:
        return []

    try:
        # Пробуем использовать оригинальную функцию
        plan = create_plan(valid_notes, free_time, mood)
        return plan if plan else []
    except IndexError as e:
        logger.error(f"IndexError в create_plan: {e}")
        # Используем резервный алгоритм при ошибке индекса
        return backup_create_plan(valid_notes, free_time, mood)
    except Exception as e:
        logger.error(f"Ошибка в create_plan: {e}")
        # Используем резервный алгоритм при любой другой ошибке
        return backup_create_plan(valid_notes, free_time, mood)


def backup_create_plan(notes, free_time, mood=""):
    """Резервный алгоритм создания плана"""
    if not notes:
        return []

    # Сортируем заметки по эффективности (приоритет/время)
    sorted_notes = []
    for note in notes:
        if note.len_note and note.len_note > 0:
            priority = note.return_prior2(mood, free_time)
            efficiency = priority / note.len_note if note.len_note > 0 else 0
            sorted_notes.append((efficiency, note))

    # Сортируем по эффективности (по убыванию)
    sorted_notes.sort(key=lambda x: x[0], reverse=True)

    # Формируем план
    plan = []
    time_used = 0

    for efficiency, note in sorted_notes:
        if time_used + note.len_note <= free_time:
            plan.append(note)
            time_used += note.len_note
        else:
            # Проверяем, можно ли добавить делимое дело частично
            if "делимо" in note.tags and note.len_note > 0:
                remaining_time = free_time - time_used
                if remaining_time > 0:
                    # Создаем частичную копию заметки
                    partial_note = Note(
                        f"{note.name} (частично)",
                        note.desc,
                        note.prior,
                        note.tags,
                        remaining_time,
                        note.date
                    )
                    plan.append(partial_note)
                    time_used += remaining_time
            break

    return plan


def safe_rec_note(notes, mood="", free_time=9999999):
    """Безопасная версия rec_note с обработкой None значений"""
    valid_notes = [note for note in notes if note.len_note is not None]

    if not valid_notes:
        return []

    try:
        return rec_note(valid_notes, mood, free_time)
    except Exception as e:
        logger.error(f"Ошибка в rec_note: {e}")
        # Простая сортировка по приоритету
        return sorted(valid_notes, key=lambda x: x.return_prior2(mood, free_time), reverse=True)


# --- Рекомендация дел ---
async def recommend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = json_to_notes(user_id)
    if not notes:
        await safe_send_message(update,
                                "У вас нет заметок для рекомендаций. Сначала создайте заметки с помощью /add_note")
        return ConversationHandler.END

    # Проверяем, есть ли заметки с указанным временем
    notes_with_time = [note for note in notes if note.len_note and note.len_note > 0]
    if not notes_with_time:
        await safe_send_message(update,
                                "У ваших заметок не указано время выполнения. Укажите время при создании заметок.")
        return ConversationHandler.END

    mood_list = list(mood_to_tags.keys())
    mood_text = "Выберите номер настроения:\n" + "\n".join([f"{i + 1}. {m}" for i, m in enumerate(mood_list)])
    await safe_send_message(update, mood_text)
    context.user_data["mood_list"] = mood_list
    return REC_MOOD


async def recommend_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mood_index = int(update.message.text) - 1
        if 0 <= mood_index < len(context.user_data["mood_list"]):
            context.user_data["mood"] = context.user_data["mood_list"][mood_index]
            await safe_send_message(update, "Введите доступное время в минутах:")
            return REC_TIME
        else:
            await safe_send_message(update, "Неверный номер. Попробуйте снова:")
            return REC_MOOD
    except:
        await safe_send_message(update, "Введите номер настроения:")
        return REC_MOOD


async def recommend_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        free_time = int(update.message.text)
        if free_time <= 0:
            await safe_send_message(update, "Введите положительное число минут:")
            return REC_TIME

        user_id = update.effective_user.id
        notes = json_to_notes(user_id)
        mood = context.user_data.get("mood", "")
        recommended_notes = safe_rec_note(notes, mood, free_time)

        if not recommended_notes:
            await safe_send_message(update, "Нет подходящих дел для рекомендации.")
            return ConversationHandler.END

        msg = f"Рекомендуемые дела (настроение: {mood}, время: {free_time} мин):\n\n"
        for i, note in enumerate(recommended_notes[:5], 1):  # Показываем топ-5
            prior2 = note.return_prior2(mood, free_time)
            time_info = f"{note.len_note} мин" if note.len_note else "время не указано"
            msg += f"{i}. {note.name} (приоритет: {prior2}, {time_info})\n"

        await safe_send_message(update, msg)
        return ConversationHandler.END

    except:
        await safe_send_message(update, "Введите число минут:")
        return REC_TIME


# --- Создание плана ---
async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = json_to_notes(user_id)
    if not notes:
        await safe_send_message(update,
                                "У вас нет заметок для создания плана. Сначала создайте заметки с помощью /add_note")
        return ConversationHandler.END

    # Проверяем, есть ли заметки с указанным временем
    notes_with_time = [note for note in notes if note.len_note and note.len_note > 0]
    if not notes_with_time:
        await safe_send_message(update,
                                "У ваших заметок не указано время выполнения. Укажите время при создании заметок.")
        return ConversationHandler.END

    mood_list = list(mood_to_tags.keys())
    mood_text = "Выберите номер настроения:\n" + "\n".join([f"{i + 1}. {m}" for i, m in enumerate(mood_list)])
    await safe_send_message(update, mood_text)
    context.user_data["mood_list"] = mood_list
    return PLAN_MOOD


async def plan_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mood_index = int(update.message.text) - 1
        if 0 <= mood_index < len(context.user_data["mood_list"]):
            context.user_data["mood"] = context.user_data["mood_list"][mood_index]
            await safe_send_message(update, "Введите доступное время для плана в минутах:")
            return PLAN_TIME
        else:
            await safe_send_message(update, "Неверный номер. Попробуйте снова:")
            return PLAN_MOOD
    except:
        await safe_send_message(update, "Введите номер настроения:")
        return PLAN_MOOD


async def plan_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        free_time = int(update.message.text)
        if free_time <= 0:
            await safe_send_message(update, "Введите положительное число минут:")
            return PLAN_TIME

        user_id = update.effective_user.id
        notes = json_to_notes(user_id)
        mood = context.user_data.get("mood", "")
        plan_notes = safe_create_plan(notes, free_time, mood)

        if not plan_notes:
            await safe_send_message(update, "Не удалось создать план. Возможно, нет подходящих дел.")
            return ConversationHandler.END

        total_time = 0
        msg = f"Ваш план (настроение: {mood}, общее время: {free_time} мин):\n\n"
        for i, note in enumerate(plan_notes, 1):
            note_time = note.len_note if note.len_note else 0
            total_time += note_time
            time_info = f"{note_time} мин" if note_time > 0 else "время не указано"
            tags_info = ', '.join(note.tags) if note.tags else "нет тегов"
            msg += f"{i}. {note.name} ({time_info}) - {tags_info}\n"

        msg += f"\nОбщее время плана: {total_time} мин"
        if total_time < free_time:
            msg += f"\nОсталось свободного времени: {free_time - total_time} мин"

        await safe_send_message(update, msg)
        return ConversationHandler.END

    except Exception as e:
        await safe_send_message(update, f"Ошибка при создании плана: {e}")
        return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    try:
        raise context.error
    except TimedOut:
        logger.error("Таймаут при отправке сообщения")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")


def main():
    logger.info("Запуск бота...")

    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Базовые команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_notes))
    application.add_handler(CommandHandler("note", show_note))
    application.add_handler(CommandHandler("delete", delete_note))

    # Обработчик создания заметок
    conv_handler_note = ConversationHandler(
        entry_points=[CommandHandler("add_note", add_note_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)],
            ADD_PRIOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_prior)],
            ADD_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tags)],
            ADD_LEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_len)],
            ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_note)

    # Обработчик рекомендаций
    conv_handler_recommend = ConversationHandler(
        entry_points=[CommandHandler("recommend", recommend_start)],
        states={
            REC_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recommend_mood)],
            REC_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recommend_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_recommend)

    # Обработчик создания плана
    conv_handler_plan = ConversationHandler(
        entry_points=[CommandHandler("plan", plan_start)],
        states={
            PLAN_MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_mood)],
            PLAN_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_plan)

    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":

    main()
