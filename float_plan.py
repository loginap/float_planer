import time
from datetime import datetime
from moods import mood_to_tags

notes = []

def rec_note(notes, mood="", free_time=9999999): #Возвращает список дел, отсортированный по вторичному приоритету
    priors_notes = []
    for note in notes:
        priors_notes.append(note.return_prior2(mood,free_time))
    priors_notes = sorted(priors_notes)[::-1]
    rec_notes = []
    for pr in priors_notes:
        for note in notes:
            if note.return_prior2(mood, free_time) == pr and note not in rec_notes:
                rec_notes.append(note)
                break
    return rec_notes

def rec_time_note(notes, mood="", free_time=9999999, tag=""): # Возвращает приоритет деленый
    priors_notes = []
    for note in notes:

        if note.len_note != None and (tag!=  "" and tag in note.tags or tag == ""):
            priors_notes.append(note)
    priors = []
    for note in priors_notes:
        priors.append(note.return_prior2(mood,free_time)/ note.len_note/note.coef_del)
    priors = sorted(priors)[::-1]
    sort_notes = []
    for j in priors:
        for note in priors_notes:
            if note.return_prior2(mood,free_time)/ note.len_note/note.coef_del == j and note.return_prior2(mood,free_time) not in sort_notes:
                sort_notes.append(note)

    return [priors, sort_notes]

def create_plan(notes, free_time, mood=""):
    sr_inf = rec_time_note(notes, mood=mood, free_time=free_time, tag="делимо")
    time = free_time
    rec_notes = []

    rec = rec_note(notes, mood=mood, free_time=free_time)[0]
    i = 0
    while rec.len_note < time and rec.prior/ rec.len_note/rec.coef_del > sr_inf[0][0]:
        time-= rec.len_note
        rec_notes.append(rec)
        i+= 1

        rec = rec_note(notes, mood=mood, free_time=free_time)[i]
    rec_notes.append(sr_inf[1][0])
    if sr_inf[1][0].len_note < time and len(notes)>1:
        time-= sr_inf[1][0].len_note
        rec_notes+= create_plan([u for u in notes if u not in rec_notes], time, mood=mood)
    else:
        time = 0

    return rec_notes

class Note:
    def __init__(self,name: str, description:str, prior:int, tags: list or None, len_note=None, date=None, coef_del=1):
        self.name = name
        self.desc = description
        self.tags = tags
        self.prior = prior
        self.len_note = len_note
        self.date = date
        self.coef_del = coef_del
    def return_prior2(self,mood: str, free_time:int):
        pr = self.prior
        if self.len_note != None and self.len_note > free_time:
            pr //= 2
        if mood in mood_to_tags:
            for md in mood_to_tags[mood]:
                if md["tag"] in self.tags:
                    pr += md["impact"]
        return pr




# Тестовые данные
note1 = Note("Заметка 1", "Описание 1", 40, ["творческая"], len_note=30)
note2 = Note("Заметка 2", "Описание 2", 1, ["скучное", "делимо"], len_note=20)
note3 = Note("Заметка 3", "Описание 3", 5, ["быстрое", "делимо"], len_note=10)
note4 = Note("Заметка 4", "Описание 4", 0, ["делимо"], len_note=60)
notes = [note1, note2, note3, note4]

# Тестирование функций
print("=== Проверка return_prior2 ===")
for note in notes:
    print(f"{note.name}: {note.return_prior2("Полон энергии", 250)}")

print("\n=== Проверка rec_note ===")
recommended = rec_note(notes, mood="Полон энергии", free_time=25)
for note in recommended:
    print(f"{note.name}: приоритет {note.return_prior2("Полон энергии", 25)}")

print("\n=== Проверка rec_time_note ===")
nts = rec_time_note(notes, mood="Полон энергии", free_time=25, tag="делимо")
print("Приоритеты:", nts[0])
print("Заметки:")
#print(nts)
for note in nts[1]:
    print(note.name)

print("\n=== Проверка create_plan ===")
plan = create_plan(notes, free_time=1000, mood="Полон энергии")
print("План:")
for note in plan:
    print(note.name)
