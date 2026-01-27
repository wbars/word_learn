#!/usr/bin/env python3
"""Quick vocabulary assessment to determine Dutch level.

Usage: python scripts/assess_vocabulary.py
Takes ~10-15 minutes. Answer y/n/p for each word.
"""

import json
import random
from datetime import datetime
from pathlib import Path

# Dutch words organized by frequency bands
# Sources: frequency lists from Dutch corpora
FREQUENCY_BANDS = {
    "top_50": [
        "de", "het", "een", "van", "en", "in", "is", "op", "te", "dat",
        "zijn", "voor", "met", "niet", "aan", "er", "maar", "om", "ook", "als",
        "dan", "naar", "kan", "dit", "nog", "wel", "geen", "meer", "al", "worden",
        "moet", "bij", "zo", "hun", "uit", "jaar", "heeft", "over", "zou", "zeer",
        "hebben", "deze", "door", "tegen", "onder", "wordt", "veel", "waar", "na", "nu"
    ],
    "top_100": [
        "goed", "maken", "komen", "gaan", "zien", "laten", "staan", "vinden", "houden", "geven",
        "nemen", "zeggen", "weten", "denken", "zullen", "mogen", "willen", "moeten", "kunnen", "doen",
        "groot", "klein", "nieuw", "oud", "lang", "kort", "hoog", "laag", "eerste", "laatste",
        "ander", "eigen", "heel", "zelf", "elke", "beide", "enkele", "alle", "weg", "tijd"
    ],
    "top_200": [
        "water", "huis", "stad", "land", "werk", "dag", "nacht", "week", "maand", "leven",
        "vraag", "antwoord", "woord", "naam", "plaats", "deel", "kant", "hoofd", "hand", "oog",
        "vrouw", "man", "kind", "vader", "moeder", "vriend", "mens", "groep", "geld", "uur",
        "beginnen", "blijven", "brengen", "eten", "drinken", "slapen", "lopen", "rijden", "schrijven", "lezen"
    ],
    "top_500": [
        "school", "straat", "kamer", "deur", "raam", "tafel", "stoel", "bed", "auto", "trein",
        "vliegtuig", "fiets", "telefoon", "computer", "boek", "brief", "krant", "film", "muziek", "sport",
        "dokter", "ziekenhuis", "winkel", "restaurant", "hotel", "station", "luchthaven", "strand", "berg", "bos",
        "rood", "blauw", "groen", "geel", "wit", "zwart", "warm", "koud", "mooi", "lelijk"
    ],
    "top_1000": [
        "ontbijt", "lunch", "avondeten", "brood", "kaas", "vlees", "vis", "groente", "fruit", "soep",
        "koffie", "thee", "bier", "wijn", "melk", "suiker", "zout", "boter", "ei", "rijst",
        "betalen", "kopen", "verkopen", "huren", "lenen", "sparen", "verdienen", "uitgeven", "kosten", "prijs",
        "vergaderen", "bespreken", "beslissen", "plannen", "organiseren", "controleren", "rapporteren", "presenteren", "analyseren", "evalueren"
    ],
    "top_2000": [
        "solliciteren", "ontslaan", "promoveren", "onderhandelen", "samenwerken", "delegeren", "motiveren", "beoordelen", "feedback", "deadline",
        "verhuizen", "verbouwen", "schilderen", "repareren", "schoonmaken", "stofzuigen", "wassen", "strijken", "koken", "bakken",
        "zwemmen", "fietsen", "hardlopen", "wandelen", "klimmen", "skiën", "tennissen", "voetballen", "trainen", "oefenen",
        "onderzoeken", "ontdekken", "ontwikkelen", "verbeteren", "uitvinden", "experimenteren", "bewijzen", "concluderen", "publiceren", "citeren"
    ],
    "top_3000": [
        "hypotheek", "verzekering", "belasting", "dividend", "investering", "inflatie", "recessie", "economie", "begroting", "subsidie",
        "democratie", "verkiezing", "parlement", "regering", "minister", "burgemeester", "rechtbank", "advocaat", "wetgeving", "grondwet",
        "klimaatverandering", "duurzaamheid", "recycling", "vervuiling", "uitstoot", "biodiversiteit", "ecosysteem", "natuurgebied", "bescherming", "uitsterven",
        "algoritme", "database", "programmeren", "software", "hardware", "netwerk", "server", "browser", "applicatie", "interface"
    ]
}

# Russian translations for verification display
TRANSLATIONS = {
    # top_50
    "de": "определённый артикль", "het": "определённый артикль (ср.р.)", "een": "неопределённый артикль",
    "van": "от, из", "en": "и", "in": "в", "is": "есть (быть)", "op": "на", "te": "слишком, чтобы",
    "dat": "что, тот", "zijn": "быть, его", "voor": "для, перед", "met": "с", "niet": "не",
    "aan": "к, на", "er": "там", "maar": "но", "om": "вокруг, чтобы", "ook": "тоже",
    "als": "как, если", "dan": "тогда, чем", "naar": "к, в", "kan": "может", "dit": "это",
    "nog": "ещё", "wel": "ведь, хорошо", "geen": "никакой", "meer": "больше", "al": "уже",
    "worden": "становиться", "moet": "должен", "bij": "у, при", "zo": "так", "hun": "их",
    "uit": "из", "jaar": "год", "heeft": "имеет", "over": "о, через", "zou": "бы",
    "zeer": "очень", "hebben": "иметь", "deze": "этот", "door": "через, посредством",
    "tegen": "против", "onder": "под", "wordt": "становится", "veel": "много", "waar": "где",
    "na": "после", "nu": "сейчас",
    # top_100
    "goed": "хороший", "maken": "делать", "komen": "приходить", "gaan": "идти", "zien": "видеть",
    "laten": "позволять", "staan": "стоять", "vinden": "находить", "houden": "держать", "geven": "давать",
    "nemen": "брать", "zeggen": "говорить", "weten": "знать", "denken": "думать", "zullen": "буду (вспом.)",
    "mogen": "мочь (разрешение)", "willen": "хотеть", "moeten": "должен", "kunnen": "мочь (способность)", "doen": "делать",
    "groot": "большой", "klein": "маленький", "nieuw": "новый", "oud": "старый", "lang": "длинный/долгий",
    "kort": "короткий", "hoog": "высокий", "laag": "низкий", "eerste": "первый", "laatste": "последний",
    "ander": "другой", "eigen": "собственный", "heel": "целый, очень", "zelf": "сам", "elke": "каждый",
    "beide": "оба", "enkele": "несколько", "alle": "все", "weg": "дорога, прочь", "tijd": "время",
    # top_200
    "water": "вода", "huis": "дом", "stad": "город", "land": "страна", "werk": "работа",
    "dag": "день", "nacht": "ночь", "week": "неделя", "maand": "месяц", "leven": "жизнь",
    "vraag": "вопрос", "antwoord": "ответ", "woord": "слово", "naam": "имя", "plaats": "место",
    "deel": "часть", "kant": "сторона", "hoofd": "голова", "hand": "рука", "oog": "глаз",
    "vrouw": "женщина", "man": "мужчина", "kind": "ребёнок", "vader": "отец", "moeder": "мать",
    "vriend": "друг", "mens": "человек", "groep": "группа", "geld": "деньги", "uur": "час",
    "beginnen": "начинать", "blijven": "оставаться", "brengen": "приносить", "eten": "есть", "drinken": "пить",
    "slapen": "спать", "lopen": "ходить/бежать", "rijden": "ехать", "schrijven": "писать", "lezen": "читать",
    # top_500
    "school": "школа", "straat": "улица", "kamer": "комната", "deur": "дверь", "raam": "окно",
    "tafel": "стол", "stoel": "стул", "bed": "кровать", "auto": "машина", "trein": "поезд",
    "vliegtuig": "самолёт", "fiets": "велосипед", "telefoon": "телефон", "computer": "компьютер", "boek": "книга",
    "brief": "письмо", "krant": "газета", "film": "фильм", "muziek": "музыка", "sport": "спорт",
    "dokter": "врач", "ziekenhuis": "больница", "winkel": "магазин", "restaurant": "ресторан", "hotel": "отель",
    "station": "станция", "luchthaven": "аэропорт", "strand": "пляж", "berg": "гора", "bos": "лес",
    "rood": "красный", "blauw": "синий", "groen": "зелёный", "geel": "жёлтый", "wit": "белый",
    "zwart": "чёрный", "warm": "тёплый", "koud": "холодный", "mooi": "красивый", "lelijk": "некрасивый",
    # top_1000
    "ontbijt": "завтрак", "lunch": "обед", "avondeten": "ужин", "brood": "хлеб", "kaas": "сыр",
    "vlees": "мясо", "vis": "рыба", "groente": "овощи", "fruit": "фрукты", "soep": "суп",
    "koffie": "кофе", "thee": "чай", "bier": "пиво", "wijn": "вино", "melk": "молоко",
    "suiker": "сахар", "zout": "соль", "boter": "масло", "ei": "яйцо", "rijst": "рис",
    "betalen": "платить", "kopen": "покупать", "verkopen": "продавать", "huren": "арендовать", "lenen": "занимать",
    "sparen": "копить", "verdienen": "зарабатывать", "uitgeven": "тратить", "kosten": "стоить", "prijs": "цена",
    "vergaderen": "собираться", "bespreken": "обсуждать", "beslissen": "решать", "plannen": "планировать",
    "organiseren": "организовывать", "controleren": "проверять", "rapporteren": "докладывать",
    "presenteren": "презентовать", "analyseren": "анализировать", "evalueren": "оценивать",
    # top_2000
    "solliciteren": "подавать заявку на работу", "ontslaan": "увольнять", "promoveren": "повышать",
    "onderhandelen": "вести переговоры", "samenwerken": "сотрудничать", "delegeren": "делегировать",
    "motiveren": "мотивировать", "beoordelen": "оценивать", "feedback": "обратная связь", "deadline": "крайний срок",
    "verhuizen": "переезжать", "verbouwen": "перестраивать", "schilderen": "красить/рисовать",
    "repareren": "ремонтировать", "schoonmaken": "убирать", "stofzuigen": "пылесосить",
    "wassen": "стирать/мыть", "strijken": "гладить", "koken": "готовить", "bakken": "печь",
    "zwemmen": "плавать", "fietsen": "кататься на велосипеде", "hardlopen": "бегать",
    "wandelen": "гулять", "klimmen": "лазить", "skiën": "кататься на лыжах",
    "tennissen": "играть в теннис", "voetballen": "играть в футбол", "trainen": "тренировать", "oefenen": "практиковать",
    "onderzoeken": "исследовать", "ontdekken": "открывать", "ontwikkelen": "развивать",
    "verbeteren": "улучшать", "uitvinden": "изобретать", "experimenteren": "экспериментировать",
    "bewijzen": "доказывать", "concluderen": "заключать", "publiceren": "публиковать", "citeren": "цитировать",
    # top_3000
    "hypotheek": "ипотека", "verzekering": "страховка", "belasting": "налог", "dividend": "дивиденд",
    "investering": "инвестиция", "inflatie": "инфляция", "recessie": "рецессия", "economie": "экономика",
    "begroting": "бюджет", "subsidie": "субсидия",
    "democratie": "демократия", "verkiezing": "выборы", "parlement": "парламент", "regering": "правительство",
    "minister": "министр", "burgemeester": "мэр", "rechtbank": "суд", "advocaat": "адвокат",
    "wetgeving": "законодательство", "grondwet": "конституция",
    "klimaatverandering": "изменение климата", "duurzaamheid": "устойчивость", "recycling": "переработка",
    "vervuiling": "загрязнение", "uitstoot": "выбросы", "biodiversiteit": "биоразнообразие",
    "ecosysteem": "экосистема", "natuurgebied": "природная территория", "bescherming": "защита", "uitsterven": "вымирание",
    "algoritme": "алгоритм", "database": "база данных", "programmeren": "программировать",
    "software": "программное обеспечение", "hardware": "аппаратное обеспечение", "netwerk": "сеть",
    "server": "сервер", "browser": "браузер", "applicatie": "приложение", "interface": "интерфейс"
}


def run_assessment():
    """Run interactive vocabulary assessment."""
    print("=" * 60)
    print("  DUTCH VOCABULARY ASSESSMENT")
    print("=" * 60)
    print()
    print("For each Dutch word, answer:")
    print("  y = I know this word (can translate to Russian)")
    print("  n = I don't know this word")
    print("  p = I partially know it (recognize but unsure)")
    print("  q = quit assessment")
    print()
    print("This will take about 10-15 minutes.")
    print("=" * 60)
    input("Press Enter to start...")
    print()

    results = {band: {"know": 0, "partial": 0, "unknown": 0, "total": 0}
               for band in FREQUENCY_BANDS}
    all_responses = []

    bands_order = ["top_50", "top_100", "top_200", "top_500", "top_1000", "top_2000", "top_3000"]

    word_count = 0
    quit_assessment = False

    for band in bands_order:
        if quit_assessment:
            break

        words = FREQUENCY_BANDS[band].copy()
        random.shuffle(words)

        # Sample size per band (adaptive)
        if band in ["top_50", "top_100"]:
            sample_size = 10  # Test more thoroughly for basic words
        elif band in ["top_200", "top_500"]:
            sample_size = 8
        else:
            sample_size = 6

        sample = words[:sample_size]

        band_label = band.replace("_", " ").title()
        print(f"\n--- {band_label} frequency words ---\n")

        for word in sample:
            word_count += 1
            translation = TRANSLATIONS.get(word, "")

            while True:
                response = input(f"  {word_count}. {word} ? [y/n/p/q]: ").strip().lower()
                if response in ['y', 'n', 'p', 'q']:
                    break
                print("     Please enter y, n, p, or q")

            if response == 'q':
                quit_assessment = True
                break

            results[band]["total"] += 1
            if response == 'y':
                results[band]["know"] += 1
                status = "know"
            elif response == 'p':
                results[band]["partial"] += 1
                status = "partial"
            else:
                results[band]["unknown"] += 1
                status = "unknown"
                # Show translation for unknown words
                if translation:
                    print(f"     → {translation}")

            all_responses.append({
                "word": word,
                "band": band,
                "response": response,
                "translation": translation
            })

        # Early termination if struggling with this band
        if results[band]["total"] >= 4:
            know_rate = results[band]["know"] / results[band]["total"]
            if know_rate < 0.3:
                print(f"\n  (Skipping harder words - found your level)")
                break

    # Calculate and display results
    print("\n" + "=" * 60)
    print("  ASSESSMENT RESULTS")
    print("=" * 60)

    total_know = sum(r["know"] for r in results.values())
    total_partial = sum(r["partial"] for r in results.values())
    total_unknown = sum(r["unknown"] for r in results.values())
    total_tested = total_know + total_partial + total_unknown

    print(f"\nWords tested: {total_tested}")
    print(f"Known:        {total_know} ({100*total_know/total_tested:.0f}%)")
    print(f"Partial:      {total_partial} ({100*total_partial/total_tested:.0f}%)")
    print(f"Unknown:      {total_unknown} ({100*total_unknown/total_tested:.0f}%)")

    print("\nBy frequency band:")
    estimated_vocab = 0
    for band in bands_order:
        r = results[band]
        if r["total"] > 0:
            know_pct = 100 * r["know"] / r["total"]
            band_size = int(band.split("_")[1])
            estimated_in_band = int(band_size * r["know"] / r["total"])
            estimated_vocab = max(estimated_vocab, estimated_in_band)
            print(f"  {band:12} - Know: {r['know']:2}/{r['total']:2} ({know_pct:5.1f}%) ≈ {estimated_in_band} words")

    # Estimate level
    if estimated_vocab < 100:
        level = "A1 Beginner"
        start_batch = 1
    elif estimated_vocab < 500:
        level = "A1-A2 Elementary"
        start_batch = 3
    elif estimated_vocab < 1500:
        level = "A2-B1 Pre-Intermediate"
        start_batch = 8
    elif estimated_vocab < 3000:
        level = "B1 Intermediate"
        start_batch = 15
    else:
        level = "B2+ Upper-Intermediate"
        start_batch = 25

    print(f"\nEstimated vocabulary size: ~{estimated_vocab} words")
    print(f"Estimated level: {level}")
    print(f"Recommended starting batch: {start_batch}")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_tested": total_tested,
        "total_know": total_know,
        "total_partial": total_partial,
        "total_unknown": total_unknown,
        "estimated_vocab": estimated_vocab,
        "estimated_level": level,
        "start_batch": start_batch,
        "by_band": results,
        "responses": all_responses,
        "unknown_words": [r["word"] for r in all_responses if r["response"] == "n"]
    }

    output_path = Path("assessment_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_path}")
    print("\nUnknown words (candidates for first batches):")
    for r in all_responses:
        if r["response"] == "n":
            print(f"  - {r['word']}: {r['translation']}")

    return output


if __name__ == "__main__":
    run_assessment()
