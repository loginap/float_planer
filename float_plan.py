import time
from datetime import datetime
from moods import mood_to_tags
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

notes = []
TOKEN = "7516925402:AAH2GjXKDeuhrFI31v4Gy_T9EeVOXYVcBuk"


# Ваши существующие функции (оставлены без изменений)
def rec_note(notes, mood="", free_time=9999999):
    priors_notes = []
    for note in notes:
        priors_notes.append(note.return_prior2(mood, free_time))
    priors_notes = sorted(priors_notes)[::-1]
    rec_notes = []
    for pr in priors_notes:
        for note in notes:
            if note.return_prior2(mood, free_time) == pr and note not in rec_notes:
                rec_notes.append(note)
                break
    return rec_notes


def rec_time_note(notes, mood="", free_time=9999999, tag=""):
    priors_notes = []
    for note in notes:
        if note.len_note != None and (tag != "" and tag in note.tags or tag == ""):
            priors_notes.append(note)
    priors = []
    for note in priors_notes:
        priors.append(note.return_prior2(mood, free_time) / note.len_note / note.coef_del)
    priors = sorted(priors)[::-1]
    sort_notes = []
    for j in priors:
        for note in priors_notes:
            if note.return_prior2(mood, free_time) / note.len_note / note.coef_del == j and note.return_prior2(mood,
                                                                                                               free_time) not in sort_notes:
                sort_notes.append(note)
    return [priors, sort_notes]


def create_plan(notes, free_time, mood=""):
    sr_inf = rec_time_note(notes, mood=mood, free_time=free_time, tag="делимо")
    time = free_time
    rec_notes = []
    rec = rec_note(notes, mood=mood, free_time=free_time)[0]
    i = 0
    while rec.len_note < time and rec.prior / rec.len_note / rec.coef_del > sr_inf[0][0]:
        time -= rec.len_note
        rec_notes.append(rec)
        i += 1
        rec = rec_note(notes, mood=mood, free_time=free_time)[i]
    rec_notes.append(sr_inf[1][0])
    if sr_inf[1][0].len_note < time and len(notes) > 1:
        time -= sr_inf[1][0].len_note
        rec_notes += create_plan([u for u in notes if u not in rec_notes], time, mood=mood)
    else:
        time = 0
    return rec_notes


class Note:
    def __init__(self, name: str, description: str, prior: int, tags: list or None, len_note=None, date=None,
                 coef_del=1):
        self.name = name
        self.desc = description
        self.tags = tags
        self.prior = prior
        self.len_note = len_note
        self.date = date
        self.coef_del = coef_del

    def return_prior2(self, mood: str, free_time: int):
        pr = self.prior
        if self.len_note != None and self.len_note > free_time:
            if "делимо" in self.tags:
                pr //= 2
            else:
                return 0
        if mood in mood_to_tags:
            for md in mood_to_tags[mood]:
                if md["tag"] in self.tags:
                    pr += md["impact"]
        return pr


# Обработчики для Telegram бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["/add_note", "/recommend"],
        ["/list_notes", "/help"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот для управления заметками.\n"
        "Доступные команды:\n"
        "/add_note - добавить новую заметку\n"
        "/recommend - получить рекомендации\n"
        "/list_notes - список всех заметок\n"
        "/help - помощь",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Помощь:\n"
        "/add_note - добавить заметку (укажите название, описание, приоритет, теги, длительность)\n"
        "/recommend - получить рекомендации (укажите ваше настроение и свободное время)\n"
        "/list_notes - показать все заметки\n"
        "/help - эта справка"
    )


async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Введите данные заметки в формате:\n"
                                        "Название Описание Приоритет Теги(через запятую) Длительность(мин)\n"
                                        "Пример: Прогулка Гулять в парке 5 активный,отдых 30")
        return

    try:
        name = context.args[0]
        desc = context.args[1]
        prior = int(context.args[2])
        tags = [tag.strip() for tag in context.args[3].split(",")]
        length = int(context.args[4]) if len(context.args) > 4 else None

        new_note = Note(name, desc, prior, tags, length)
        notes.append(new_note)
        await update.message.reply_text(f"Заметка '{name}' успешно добавлена!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}\nПроверьте формат ввода.")


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not notes:
        await update.message.reply_text("Нет сохраненных заметок.")
        return

    response = "Список заметок:\n\n"
    for i, note in enumerate(notes, 1):
        response += (f"{i}. {note.name}\n"
                     f"Описание: {note.desc}\n"
                     f"Приоритет: {note.prior}\n"
                     f"Теги: {', '.join(note.tags)}\n"
                     f"Длительность: {note.len_note} мин\n\n")

    await update.message.reply_text(response)


async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not notes:
        await update.message.reply_text("Нет заметок для рекомендаций. Сначала добавьте заметки.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Введите ваше настроение и свободное время в минутах:\n"
                                        "/recommend Настроение Время\n"
                                        "Пример: /recommend Полон_энергии 60")
        return

    mood = context.args[0]
    try:
        free_time = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажите время в минутах (число).")
        return

    recommended = rec_note(notes, mood=mood, free_time=free_time)
    time_efficient = rec_time_note(notes, mood=mood, free_time=free_time, tag="делимо")
    plan = create_plan(notes, free_time=free_time, mood=mood)

    response = (f"Рекомендации для настроения '{mood}' и времени {free_time} мин:\n\n"
                "Топ рекомендуемых дел:\n")

    for i, note in enumerate(recommended[:3], 1):
        response += f"{i}. {note.name} (приоритет: {note.return_prior2(mood, free_time)})\n"

    response += "\nСамые эффективные дела (приоритет/время):\n"
    for i, note in enumerate(time_efficient[1][:3], 1):
        eff = note.return_prior2(mood, free_time) / note.len_note / note.coef_del
        response += f"{i}. {note.name} ({eff:.2f} приор/мин)\n"

    response += "\nОптимальный план:\n"
    for i, note in enumerate(plan[:5], 1):
        response += f"{i}. {note.name} ({note.len_note} мин)\n"

    await update.message.reply_text(response)


def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_note", add_note))
    application.add_handler(CommandHandler("list_notes", list_notes))
    application.add_handler(CommandHandler("recommend", recommend))

    application.run_polling()


if __name__ == "__main__":
    main()