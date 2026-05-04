import logging
from ollama import AsyncClient

# Inicjalizacja asynchronicznego klienta Ollama
client = AsyncClient()


async def get_local_ai_recommendation(user_wish, found_destinations):
    """
    Wybiera najlepsze miejsce z dostępnych w bazie na podstawie życzenia użytkownika.
    """
    destinations_info = ""
    for d in found_destinations:
        destinations_info += f"- {d[1]}, {d[0]} (Budżet: {d[2]}/3)\n"

    prompt = f"""
    Jesteś ekspertem podróży. Użytkownik chce pojechać na wakacje. 
    Jego specjalne życzenie: "{user_wish}"

    Oto lista dostępnych kierunków z naszej bazy danych:
    {destinations_info}

    Twoje zadanie:
    1. Wybierz jeden, najlepiej pasujący kierunek.
    2. Napisz krótkie uzasadnienie (2-3 zdania), dlaczego to miejsce pasuje.
    3. Odpowiedz wyłącznie w języku polskim.
    """

    try:
        response = await client.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    except Exception as e:
        logging.error(f"Błąd AI Local Recommendation: {e}")
        # Zwracamy przyjazny komunikat, jeśli AI nie odpowie
        return "Niestety, AI napotkało problem przy analizie Twojego życzenia, ale powyższe miejsca z bazy wciąż są dla Ciebie idealne! ✈️"


async def get_fallback_ai_recommendation(user_data, user_wish=None):
    """
    Funkcja zapasowa (Fallback): wywoływana, gdy główna baza danych jest pusta.
    Przekazuje filtry użytkownika bezpośrednio do AI, aby wygenerować nową propozycję.
    """
    # Zbieramy filtry w czytelny tekst
    filters_text = ""
    for key, value in user_data.items():
        if value and value != '⏭ Pomiń':
            filters_text += f"- {key.replace('chosen_', '').capitalize()}: {value}\n"

    prompt = (
        "Jesteś profesjonalnym ekspertem podróżniczym. Nasza baza danych nie znalazła wyników, "
        "więc musisz polecić JEDNO idealne miejsce na świecie z własnej wiedzy.\n\n"
        f"Wymagania użytkownika:\n{filters_text}"
    )

    if user_wish:
        prompt += f"\nDodatkowe życzenie użytkownika: {user_wish}\n"

    prompt += (
        "\nUWAGA: Musisz odpowiedzieć W CAŁOŚCI w języku polskim! "
        "Odpowiedź musi być zwięzła (MAKSYMALNIE 800 znaków). "
        "ZABRONIONE JEST używanie jakichkolwiek powitań typu 'Cześć' czy 'Oto propozycja'. "
        "Twoja odpowiedź MUSI wyglądać DOKŁADNIE według tego szablonu:\n\n"
        "Miasto: [Tylko nazwa miasta, np. Phuket]\n"
        "Opis: [Twoje uzasadnienie i opis]"
    )

    try:
        response = await client.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    except Exception as e:
        # Rejestrujemy błąd, jeśli AI jest wyłączone lub wystąpił problem z siecią
        logging.error(f"Błąd AI Fallback: {e}")
        return None


async def get_city_details_ai(city_name):
    """
    Generuje unikalny i barwny opis wybranego miasta przez AI.
    """
    prompt = (
        f"Jesteś profesjonalnym przewodnikiem turystycznym. "
        f"Opowiedz krótko, ciekawie i zachęcająco o mieście {city_name}. "
        f"Wspomnij o najlepszych atrakcjach, klimacie i dlaczego warto tam pojechać. "
        f"Odpowiedź musi być zwięzła (MAKSYMALNIE 800 znaków). "
        f"UWAGA: Musisz odpowiedzieć W CAŁOŚCI w języku polskim!"
    )

    try:
        response = await client.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    except Exception as e:
        logging.error(f"Błąd AI Details: {e}")
        return None