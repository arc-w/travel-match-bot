import asyncio
import logging
import os
import urllib.parse
import textwrap
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from dotenv import load_dotenv

from db_manager import get_all_destinations
from weather_service import get_weather
from holiday_service import get_next_holiday
from ai_service import get_local_ai_recommendation, get_fallback_ai_recommendation, get_city_details_ai
from wiki_service import get_wikipedia_info

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
USE_AI = True

REGION_MAP = {
    'Europa': ['ES', 'PL', 'IT', 'NO', 'GR', 'PT', 'CH', 'FR', 'GB', 'CZ', 'HU', 'HR', 'BG', 'CY', 'MT', 'DE', 'LV',
               'LT', 'NL', 'AT', 'SK', 'RO', 'DK', 'SE'],
    'Azja': ['GE', 'TR', 'TH', 'ID', 'MV', 'AE', 'JP'],
    'Ameryka Płn.': ['US', 'CA'],
    'Ameryka Płd. i Środkowa': ['MX', 'BR', 'AR', 'PE', 'CU', 'DO'],
    'Afryka': ['MA', 'ZA', 'EG', 'KE', 'TZ'],
    'Oceania': ['AU', 'NZ', 'FJ']
}


def get_region_by_code(code):
    for region, codes in REGION_MAP.items():
        if code in codes:
            return region
    return 'Inny'


class TravelForm(StatesGroup):
    choosing_type = State()
    choosing_region = State()
    choosing_budget = State()
    choosing_popularity = State()
    choosing_climate = State()
    waiting_for_wish = State()
    waiting_for_city_details = State()


dp = Dispatcher()


def make_reply_keyboard(items: list):
    builder = ReplyKeyboardBuilder()
    for item in items:
        builder.button(text=item)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


@dp.message(CommandStart())
@dp.message(F.text == "🔄 Wyszukaj ponownie")
async def command_start_handler(message: types.Message, state: FSMContext):
    await state.clear()

    if message.text == "/start":
        text = (
            f"Cześć, {message.from_user.full_name}! 👋\n\n"
            f"Jestem Twoim inteligentnym asystentem podróży 🌍✈️\n"
            f"Wybierz parametry, a ja na podstawie zaawansowanych algorytmów znajdę coś dla Ciebie!\n\n"
            f"Jaki rodzaj wyjazdu preferujesz?"
        )
    else:
        text = "Szukamy dalej! 🕵️‍♂️ Jaki rodzaj wyjazdu preferujesz?"

    await message.answer(text, parse_mode="HTML",
                         reply_markup=make_reply_keyboard([
                             "Morze 🏖️", "Góry ⛰️", "Kultura i architektura 🏛️",
                             "Relaks 🧖‍♀️", "Rozrywka 🎢", "⏭ Pomiń"
                         ]))

    await state.set_state(TravelForm.choosing_type)


@dp.message(TravelForm.choosing_type)
async def type_chosen(message: types.Message, state: FSMContext):
    ui_to_db = {
        "Morze 🏖️": "Morze",
        "Góry ⛰️": "Góry",
        "Kultura i architektura 🏛️": "Miasto",
        "Relaks 🧖‍♀️": "Relaks",
        "Rozrywka 🎢": "Rozrywka"
    }

    db_type = ui_to_db.get(message.text, message.text)

    await state.update_data(chosen_type=db_type)
    await message.answer(
        "W jakim regionie świata? 🗺️",
        reply_markup=make_reply_keyboard([
            "Europa", "Azja", "Ameryka Płn.", "Ameryka Płd. i Środkowa",
            "Afryka", "Oceania", "⏭ Pomiń"
        ])
    )
    await state.set_state(TravelForm.choosing_region)


@dp.message(TravelForm.choosing_region)
async def region_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_region=message.text)
    await message.answer(
        "Jaki jest Twój budżet? 💸",
        reply_markup=make_reply_keyboard(["Niski 💰", "Średni 💰💰", "Wysoki 💰💰💰", "⏭ Pomiń"])
    )
    await state.set_state(TravelForm.choosing_budget)


@dp.message(TravelForm.choosing_budget)
async def budget_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_budget=message.text)
    await message.answer(
        "Wolisz znane miejsca czy ukryte perełki? 🌟",
        reply_markup=make_reply_keyboard(["Bardzo popularne 🌟🌟", "Znane 🌟", "Ukryte perełki 🤫", "⏭ Pomiń"])
    )
    await state.set_state(TravelForm.choosing_popularity)


@dp.message(TravelForm.choosing_popularity)
async def popularity_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_popularity=message.text)
    await message.answer(
        "Jakiego klimatu szukasz? 🌡️",
        reply_markup=make_reply_keyboard(["Ciepły🌡️", "Umiarkowany⛅️", "Mroźny❄️", "⏭ Pomiń"])
    )
    await state.set_state(TravelForm.choosing_climate)


@dp.message(TravelForm.choosing_climate)
async def climate_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_climate=message.text)

    if USE_AI:
        await message.answer(
            "Świetnie! Czy masz jakieś dodatkowe wymogi? ✨\n"
            "(np. 'chcę zjeść dobre sushi', 'lubię starożytne ruiny')\n\n"
            "Możesz też pominąć ten krok i od razu zobaczyć najlepsze propozycje.",
            reply_markup=make_reply_keyboard(["⏭ Pomiń"])
        )
        await state.set_state(TravelForm.waiting_for_wish)
    else:
        await skip_wish_handler(message, state)


async def get_filtered_recommendations(user_data):
    raw_destinations = get_all_destinations()
    step1_filtered = []

    for d in raw_destinations:
        country, city, d_type, d_climate, d_budget, d_popularity, lat, lon, code = d

        if user_data.get('chosen_type') not in ['⏭ Pomiń', None]:
            if d_type.lower() != user_data['chosen_type'].lower():
                continue

        if user_data.get('chosen_region') not in ['⏭ Pomiń', None]:
            if get_region_by_code(code) != user_data['chosen_region']:
                continue

        if user_data.get('chosen_budget') not in ['⏭ Pomiń', None]:
            budget_map = {'Niski 💰': 1, 'Średni 💰💰': 2, 'Wysoki 💰💰💰': 3}
            if d_budget != budget_map.get(user_data['chosen_budget']):
                continue

        if user_data.get('chosen_popularity') not in ['⏭ Pomiń', None]:
            if user_data['chosen_popularity'] == 'Bardzo popularne 🌟🌟' and d_popularity < 8:
                continue
            elif user_data['chosen_popularity'] == 'Znane 🌟' and (d_popularity < 4 or d_popularity >= 8):
                continue
            elif user_data['chosen_popularity'] == 'Ukryte perełki 🤫' and d_popularity >= 4:
                continue

        step1_filtered.append(d)

    if not step1_filtered:
        return []

    sem = asyncio.Semaphore(5)
    async def fetch_weather_safe(destination):
        async with sem:
            await asyncio.sleep(0.05)
            return await get_weather(destination[6], destination[7])

    tasks = [fetch_weather_safe(d) for d in step1_filtered]
    weathers = await asyncio.gather(*tasks)

    final_recommendations = []

    for d, weather in zip(step1_filtered, weathers):
        country, city, d_type, d_climate, d_budget, d_popularity, lat, lon, code = d
        temp = weather['temp'] if weather else None
        wind = weather['wind'] if weather else None

        if temp is not None:
            if temp < 10:
                actual_climate = "Mroźny❄️"
            elif 10 <= temp <= 23:
                actual_climate = "Umiarkowany⛅️"
            else:
                actual_climate = "Ciepły🌡️"
        else:
            actual_climate = d_climate.lower()
            if actual_climate == "ciepły": actual_climate = "Ciepły🌡️"
            elif actual_climate == "umiarkowany": actual_climate = "Umiarkowany⛅️"
            elif actual_climate == "mroźny": actual_climate = "Mroźny❄️"

        if user_data.get('chosen_climate') not in ['⏭ Pomiń', None]:
            if actual_climate != user_data['chosen_climate']:
                continue

        final_recommendations.append((country, city, d_budget, lat, lon, code, temp, d_popularity, wind))

    return final_recommendations


@dp.message(TravelForm.waiting_for_wish, F.text == "⏭ Pomiń")
async def skip_wish_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    skipped = ['⏭ Pomiń', None]
    if (user_data.get('chosen_type') in skipped and
            user_data.get('chosen_region') in skipped and
            user_data.get('chosen_budget') in skipped and
            user_data.get('chosen_popularity') in skipped and
            user_data.get('chosen_climate') in skipped):
        await message.answer(
            "Nie wybrano żadnych filtrów ani wymogów. Spróbuj wyszukać ponownie, wybierając chociaż jedno kryterium! 😅",
            reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"])
        )
        await state.set_state(None)
        return

    status_msg = await message.answer("Skanuję świat... 🌍⏳",
                                      reply_markup=ReplyKeyboardRemove())

    recommendations = await get_filtered_recommendations(user_data)
    await status_msg.delete()

    if not recommendations:
        if USE_AI:
            ai_status = await message.answer(
                "Baza danych nie znalazła idealnego dopasowania. Przeszukuję ukryte perełki z całego świata... 🌍🔍")
            try:
                ai_suggestion = await get_fallback_ai_recommendation(user_data, user_wish=None)
                await ai_status.delete()

                if ai_suggestion:
                    lines = [line.strip() for line in ai_suggestion.strip().split('\n') if line.strip()]
                    city_name = lines[0]

                    for line in lines:
                        if line.lower().startswith("miasto:"):
                            city_name = line.split(":", 1)[1].strip()
                            break

                    description = ai_suggestion.replace(f"Miasto: {city_name}", "").replace("Miasto:", "").replace(
                        "Opis:", "").strip()
                    description = '\n'.join([line.strip() for line in description.split('\n') if line.strip()])

                    await state.update_data(last_cities=[city_name])

                    _, wiki_image = await get_wikipedia_info(city_name)
                    final_text = f"✨ <b>Znalazłem coś specjalnie dla Ciebie:</b>\n\n<b>{city_name}</b>\n{description}\n\nUdanej podróży! ✈️"

                    if wiki_image:
                        await message.answer_photo(photo=wiki_image)

                    await message.answer(final_text, parse_mode="HTML",
                                         reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
                else:
                    await message.answer(
                        "Niestety, nie znalazłem ofert, a mój rozszerzony system jest obecnie niedostępny. Spróbuj zmienić parametry! 😕",
                        reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
            except Exception:
                await ai_status.delete()
                await message.answer("Niestety, wystąpił błąd. Spróbuj zmienić parametry! 😕",
                                     reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
        else:
            await message.answer(
                "Niestety, nie znalazłem ofert w bazie, a mój rozszerzony system jest obecnie niedostępny. Spróbuj zmienić parametry! 😕",
                reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"])
            )
    else:
        city_names = [item[1] for item in recommendations[:10]]
        await state.update_data(last_cities=city_names)

        response_text = "Oto najlepsze propozycje dla Ciebie na TEN MOMENT: ✈️\n\n"
        for item in recommendations[:10]:
            country, city, cost, lat, lon, code, temp, d_popularity, wind = item
            holiday = await get_next_holiday(code)

            temp_info = f"{temp}°C" if temp is not None else "brak danych"
            wind_info = f"{wind} km/h" if wind is not None else "brak danych"
            money = "💰" * cost
            budget_labels = {1: "Niski", 2: "Średni", 3: "Wysoki"}
            budget_text = budget_labels.get(cost, "Nieznany")
            if d_popularity >= 8:
                pop_stars = "🌟🌟 (Bardzo popularne)"
            elif d_popularity >= 4:
                pop_stars = "🌟 (Znane)"
            else:
                pop_stars = "🤫 (Ukryte perełki)"

            if holiday != "brak danych":
                query = urllib.parse.quote_plus(f"{holiday} {country}")
                holiday_link = f"<a href='https://www.google.com/search?q={query}'>{holiday}</a>"
                holiday_display = f"\n🎉 <b>Uwaga na święto:</b> {holiday_link} <i>(możliwe zamknięte sklepy!)</i>"
            else:
                holiday_display = ""

            maps_query = urllib.parse.quote_plus(f"{city}, {country}")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

            response_text += (
                f"✅ <a href='{maps_url}'><b>{city}, {country}</b></a> {pop_stars}\n"
                f"🌡 Pogoda: {temp_info} | 💨 Wiatr: {wind_info}"
                f"{holiday_display}\n"
                f"💵 Budżet: {money} ({budget_text})\n\n"
            )

        await message.answer(response_text, parse_mode="HTML", disable_web_page_preview=True,
                             reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie", "📖 Opowiedz mi więcej"]))

    await state.set_state(None)


@dp.message(TravelForm.waiting_for_wish)
async def process_wish(message: types.Message, state: FSMContext):
    user_wish = message.text
    user_data = await state.get_data()

    status_msg = await message.answer("Łączę Twoje filtry, pogodę i dodatkowe wymogi... ⚙️🔍",
                                      reply_markup=ReplyKeyboardRemove())

    skipped = ['⏭ Pomiń', None]
    if (user_data.get('chosen_type') in skipped and
            user_data.get('chosen_region') in skipped and
            user_data.get('chosen_budget') in skipped and
            user_data.get('chosen_popularity') in skipped and
            user_data.get('chosen_climate') in skipped):
        recommendations = []
    else:
        recommendations = await get_filtered_recommendations(user_data)

    await status_msg.delete()

    if not recommendations:
        ai_status = await message.answer(
            "Omijasz standardowe filtry! Uruchamiam globalne wyszukiwanie na podstawie Twoich dodatkowych wymog... 🌐🔍")
        try:
            ai_suggestion = await get_fallback_ai_recommendation(user_data, user_wish)
            await ai_status.delete()

            if ai_suggestion:
                lines = [line.strip() for line in ai_suggestion.strip().split('\n') if line.strip()]
                city_name = lines[0]

                for line in lines:
                    if line.lower().startswith("miasto:"):
                        city_name = line.split(":", 1)[1].strip()
                        break

                description = ai_suggestion.replace(f"Miasto: {city_name}", "").replace("Miasto:", "").replace(
                    "Opis:", "").strip()
                description = '\n'.join([line.strip() for line in description.split('\n') if line.strip()])

                await state.update_data(last_cities=[city_name])

                _, wiki_image = await get_wikipedia_info(city_name)
                final_text = f"✨ <b>Znalazłem coś specjalnie dla Ciebie:</b>\n\n<b>{city_name}</b>\n{description}\n\nUdanej podróży! ✈️"

                if wiki_image:
                    await message.answer_photo(photo=wiki_image)

                await message.answer(final_text, parse_mode="HTML",
                                     reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
            else:
                await message.answer(
                    "Niestety, nie znalazłem ofert, a system zaawansowany jest obecnie niedostępny. Spróbuj zmienić parametry! 😕",
                    reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
        except Exception:
            await ai_status.delete()
            await message.answer("Niestety, nie znalazłem ofert. Spróbuj zmienić parametry! 😕",
                                 reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"]))
    else:
        city_names = [item[1] for item in recommendations[:10]]
        await state.update_data(last_cities=city_names)

        response_text = "Oto najlepsze propozycje z bazy dopasowane do Ciebie: ✈️\n\n"
        for item in recommendations[:10]:
            country, city, cost, lat, lon, code, temp, d_popularity, wind = item
            holiday = await get_next_holiday(code)

            temp_info = f"{temp}°C" if temp is not None else "brak danych"
            wind_info = f"{wind} km/h" if wind is not None else "brak danych"
            money = "💰" * cost
            budget_labels = {1: "Niski", 2: "Średni", 3: "Wysoki"}
            budget_text = budget_labels.get(cost, "Nieznany")

            if d_popularity >= 8:
                pop_stars = "🌟🌟 (Bardzo popularne)"
            elif d_popularity >= 4:
                pop_stars = "🌟 (Znane)"
            else:
                pop_stars = "🤫 (Ukryte perełki)"

            if holiday != "brak danych":
                query = urllib.parse.quote_plus(f"{holiday} {country}")
                holiday_link = f"<a href='https://www.google.com/search?q={query}'>{holiday}</a>"
                holiday_display = f"\n🎉 <b>Uwaga na święto:</b> {holiday_link} <i>(możliwe zamknięte sklepy!)</i>"
            else:
                holiday_display = ""

            maps_query = urllib.parse.quote_plus(f"{city}, {country}")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

            response_text += (
                f"✅ <a href='{maps_url}'><b>{city}, {country}</b></a> {pop_stars}\n"
                f"🌡 Pogoda: {temp_info} | 💨 Wiatr: {wind_info}\n"
                f"{holiday_display}\n"
                f"💵 Budżet: {money} ({budget_text})\n\n"
            )

        await message.answer(
            response_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        ai_format_recs = [(r[0], r[1], r[2]) for r in recommendations]
        ai_suggestion = await get_local_ai_recommendation(user_wish, ai_format_recs)

        await message.answer(
            f"✨ <b>Moja specjalna rekomendacja:</b>\n\n{ai_suggestion}",
            parse_mode="HTML",
            reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie", "📖 Opowiedz mi więcej"])
        )

    await state.set_state(None)

@dp.message(F.text == "📖 Opowiedz mi więcej")
async def ask_for_city_details(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    last_cities = user_data.get("last_cities", [])

    if not last_cities:
        await message.answer(
            "Nie mam zapisanych żadnych miast. Spróbuj wyszukać ponownie!",
            reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie"])
        )
        return

    keyboard_items = last_cities + ["🔙 Wróć do menu"]

    await message.answer(
        "Wybierz miasto z listy poniżej, aby dowiedzieć się o nim więcej i zobaczyć zdjęcia 🏛️📸:",
        reply_markup=make_reply_keyboard(keyboard_items)
    )
    await state.set_state(TravelForm.waiting_for_city_details)


@dp.message(TravelForm.waiting_for_city_details)
async def provide_city_details(message: types.Message, state: FSMContext):
    if message.text == "🔙 Wróć do menu":
        await message.answer(
            "Wróciłeś do menu wyników.",
            reply_markup=make_reply_keyboard(["🔄 Wyszukaj ponownie", "📖 Opowiedz mi więcej"])
        )
        await state.set_state(None)
        return

    city_name = message.text
    status_msg = await message.answer(f"Przygotowuję unikalny przewodnik po {city_name}... ✍️📸",
                                      reply_markup=ReplyKeyboardRemove())

    wiki_text, wiki_image = await get_wikipedia_info(city_name)

    ai_text = None
    if USE_AI:
        ai_text = await get_city_details_ai(city_name)

    await status_msg.delete()

    user_data = await state.get_data()
    keyboard_items = user_data.get("last_cities", []) + ["🔙 Wróć do menu"]
    reply_markup = make_reply_keyboard(keyboard_items)

    if ai_text:
        text_to_send = f"✨ <b>{city_name.title()}</b>\n\n{ai_text}"
    elif wiki_text:
        text_to_send = f"📖 <b>{city_name.title()}</b>\n\n{wiki_text}"
    else:
        text_to_send = None

    if text_to_send:
        if wiki_image:
            await message.answer_photo(photo=wiki_image)

        await message.answer(text_to_send, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await message.answer(
            f"Niestety, nie znalazłem informacji o '{city_name}'.",
            reply_markup=reply_markup
        )


async def run_console_mode():
    print("\n" + "=" * 40)
    print("Cześć! Jestem Twoim inteligentnym asystentem podróży️")
    print("=" * 40)

    def get_console_choice(title, options):
        print(f"\n{title}")
        for i, option in enumerate(options, 1):
            print(f"{i} - {option}")

        while True:
            choice = input("Twój wybór (wpisz numer): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            print("Nieprawidłowy numer. Spróbuj ponownie.")

    while True:
        user_data = {}

        chosen_type_ui = get_console_choice(
            "Jaki rodzaj wyjazdu preferujesz?",
            ["Morze", "Góry", "Kultura i architektura",
             "Relaks", "Rozrywka", "⏭ Pomiń"]
        )
        ui_to_db = {
            "Morze": "Morze",
            "Góry": "Góry",
            "Kultura i architektura": "Miasto",
            "Relaks️": "Relaks",
            "Rozrywka": "Rozrywka"
        }
        user_data['chosen_type'] = ui_to_db.get(chosen_type_ui, chosen_type_ui)

        user_data['chosen_region'] = get_console_choice(
            "W jakim regionie świata?",
            ["Europa", "Azja", "Ameryka Płn.", "Ameryka Płd. i Środkowa", "Afryka", "Oceania", "⏭ Pomiń"]
        )

        user_data['chosen_budget'] = get_console_choice(
            "Jaki jest Twój budżet?",
            ["Niski", "Średni", "Wysoki", "⏭ Pomiń"]
        )

        user_data['chosen_popularity'] = get_console_choice(
            "Wolisz znane miejsca czy ukryte perełki?",
            ["Bardzo popularne", "Znane", "Ukryte perełki", "⏭ Pomiń"]
        )

        user_data['chosen_climate'] = get_console_choice(
            "Jakiego klimatu szukasz?",
            ["Ciepły", "Umiarkowany", "Mroźny", "⏭ Pomiń"]
        )

        if USE_AI:
            user_wish = input("\nDodatkowe wymogi? (Wpisz wymogi lub wciśnij Enter, aby pominąć): ").strip()
            if not user_wish:
                user_wish = None
        else:
            user_wish = None

        print("\nSkanuję świat... ")
        recommendations = await get_filtered_recommendations(user_data)

        if not recommendations:
            if USE_AI:
                print("Baza danych jest pusta. Uruchamiam AI... ")
                ai_suggestion = await get_fallback_ai_recommendation(user_data, user_wish)
                if ai_suggestion:
                    print("\nZnalazłem coś specjalnie dla Ciebie:\n")

                    wrapped_ai = "\n".join([textwrap.fill(p, width=80) for p in ai_suggestion.split('\n')])
                    print(wrapped_ai)

                    lines = [line.strip() for line in ai_suggestion.strip().split('\n') if line.strip()]
                    ai_city = lines[0]
                    for line in lines:
                        if line.lower().startswith("miasto:"):
                            ai_city = line.split(":", 1)[1].strip()
                            break

                    wiki_choice = input(f"\nCzy chcesz przeczytać o '{ai_city}'? (T/N): ").strip().upper()
                    if wiki_choice == 'T':
                        print(f"\nSzukam informacji o {ai_city}...")
                        wiki_text, _ = await get_wikipedia_info(ai_city)
                        if wiki_text:
                            wrapped_text = textwrap.fill(wiki_text, width=80)
                            print(f"\nWIKIPEDIA ({ai_city}):\n{wrapped_text}")
                        else:
                            print(f"\nBrak danych o '{ai_city}' na Wikipedii.")
                else:
                    print("Niestety, AI nie odpowiedziało.")
            else:
                print("Niestety, brak wyników w bazie, a tryb AI jest wyłączony. Spróbuj innych filtrów.")
        else:
            print("\nOto najlepsze propozycje dla Ciebie na TEN MOMENT: ")
            for i, item in enumerate(recommendations[:10], 1):
                country, city, cost, lat, lon, code, temp, d_popularity, wind = item
                temp_info = f"{temp}°C" if temp is not None else "brak danych"
                wind_info = f"{wind} km/h" if wind is not None else "brak danych"
                print(f"{i}. {city}, {country} | Pogoda: {temp_info}, Wiatr: {wind_info} | Budżet: {cost}/3")

            if user_wish and USE_AI:
                print("\nAnalizuję Twoje wymogi przez AI...")
                ai_format_recs = [(r[0], r[1], r[2]) for r in recommendations]
                ai_suggestion = await get_local_ai_recommendation(user_wish, ai_format_recs)

                wrapped_ai = "\n".join([textwrap.fill(p, width=80) for p in ai_suggestion.split('\n')])
                print(f"\nMoja specjalna rekomendacja:\n{wrapped_ai}")

            wiki_options = [item[1] for item in recommendations[:10]] + ["⏭ Pomiń"]

            detail = get_console_choice(
                "O jakim mieście chcesz dowiedzieć się więcej?",
                wiki_options
            )

            if detail != "⏭ Pomiń":
                print(f"\nSzukam informacji o {detail}...")
                wiki_text, _ = await get_wikipedia_info(detail)
                if wiki_text:
                    wrapped_text = textwrap.fill(wiki_text, width=80)
                    print(f"\nWIKIPEDIA ({detail}):\n{wrapped_text}")
                else:
                    print(f"\nBrak danych o '{detail}' na Wikipedii.")

        again = input("\nChcesz wyszukać ponownie? (T/N): ").strip().upper()
        if again != 'T':
            print("Do widzenia!")
            break


async def main():
    bot = Bot(token=TOKEN)
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nBot zatrzymany.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    print("=== KONFIGURACJA STARTOWA ===")
    print("Czy chcesz używać AI?")
    print("1 - Tak (Pełne możliwości, Llama 3)")
    print("2 - Nie (Tylko szybka baza danych i Wikipedia)")
    ai_choice = input("Twój wybór (1/2): ").strip()

    USE_AI = (ai_choice == "1")

    print("\nWybierz tryb pracy:")
    print("1 - Bot Telegram")
    print("2 - Konsola (szybki test tekstowy, bez obrazków)")
    mode = input("Twój wybór (1/2): ").strip()

    if mode == "1":
        print(f"Uruchamiam bota Telegram... (AI: {'WŁĄCZONE' if USE_AI else 'WYŁĄCZONE'})")
        logging.getLogger().setLevel(logging.INFO)
        asyncio.run(main())
    elif mode == "2":
        print(f"Uruchamiam tryb konsolowy... (AI: {'WŁĄCZONE' if USE_AI else 'WYŁĄCZONE'})")
        asyncio.run(run_console_mode())
    else:
        print("Nieznany tryb. Zamykam program.")