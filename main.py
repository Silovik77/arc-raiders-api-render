from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import requests
import logging

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- URL API для ARC Raiders ---
EVENT_SCHEDULE_API_URL = 'https://metaforge.app/api/arc-raiders/events-schedule'

# --- Словари перевода ---
EVENT_TRANSLATIONS = {
    "Electromagnetic Storm": "⚡ Электромагнитная буря",
    "Harvester": "🪴 Сборщик",
    "Lush Blooms": "🌿 Повышенная растительность",
    "Matriarch": "👑 Матриарх",
    "Night Raid": "🌙 Ночной рейд",
    "Uncovered Caches": "宝藏 Обнаруженные тайники",
    "Launch Tower Loot": "🚀 Добыча с пусковой башни",
    "Hidden Bunker": " bunker Скрытый бункер",
    "Husk Graveyard": "💀 Кладбище ARC",
    "Prospecting Probes": "📡 Геологические зонды",
    "Cold Snap": "❄️ Холодная вспышка",
    "Locked Gate": "🔒 Закрытые врата",
}

MAP_TRANSLATIONS = {
    "Dam": "Плотина",
    "Buried City": "Погребённый город",
    "Spaceport": "Космопорт",
    "Blue Gate": "Синие врата",
    "Stella Montis": "Стелла Монти",
}

# --- Функции для получения и обработки данных из API ---

def get_arc_raiders_events_from_api_schedule():
    try:
        response = requests.get(EVENT_SCHEDULE_API_URL)
        response.raise_for_status()
        data = response.json()
        raw_events = data.get('data', [])

        if raw_events and 'startTime' in raw_events[0] and 'endTime' in raw_events[0]:
            logger.info("Обнаружен формат startTime/endTime в API /events-schedule. Используем точную логику.")
            return _get_events_exact(raw_events)
        elif raw_events and 'times' in raw_events[0]:
            logger.info("Обнаружен формат times HH:MM в API /events-schedule. Используем логику расписания.")
            return _get_events_schedule(raw_events)
        else:
            logger.error("Неизвестный формат ответа API /events-schedule. Нет startTime/endTime или times.")
            return [], []

    except Exception as e:
        logger.error(f"Ошибка при получении данных из API (events-schedule): {e}")
        return [], []

def _get_events_exact(raw_events):
    active_events = []
    upcoming_events = []
    current_time_utc = datetime.now(timezone.utc)

    for event_obj in raw_events:
        name = event_obj.get('name', 'Unknown Event')
        location = event_obj.get('map', 'Unknown Location')
        start_timestamp_ms = event_obj.get('startTime')
        end_timestamp_ms = event_obj.get('endTime')

        if not start_timestamp_ms or not end_timestamp_ms:
            continue

        try:
            start_dt = datetime.fromtimestamp(start_timestamp_ms / 1000, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_timestamp_ms / 1000, tz=timezone.utc)

            if start_dt <= current_time_utc < end_dt:
                time_left = end_dt - current_time_utc
                total_seconds = int(time_left.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_parts = []
                if hours > 0: time_parts.append(f"{hours}ч")
                if minutes > 0: time_parts.append(f"{minutes}м")
                if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
                time_left_str = " ".join(time_parts)

                active_events.append({
                    'name': name,
                    'location': location,
                    'time_left': time_left_str,
                })
                continue

            if start_dt > current_time_utc:
                time_to_start = start_dt - current_time_utc
                total_seconds = int(time_to_start.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_parts = []
                if hours > 0: time_parts.append(f"{hours}ч")
                if minutes > 0: time_parts.append(f"{minutes}м")
                if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
                time_to_start_str = " ".join(time_parts)

                upcoming_events.append({
                    'name': name,
                    'location': location,
                    'time_left': time_to_start_str,
                })

        except Exception as e:
            logger.error(f"Error processing time for event {name}: {e}")
            continue

    logger.info(f"Вычисление по API (events-schedule - точная логика) завершено: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
    return active_events, upcoming_events

def _get_events_schedule(raw_events):
    active_events = []
    upcoming_events = []
    current_time_utc = datetime.now(timezone.utc)
    current_date_utc = current_time_utc.date()
    current_time_only = current_time_utc.time()

    for event_obj in raw_events:
        name = event_obj.get('name', 'Unknown Event')
        location = event_obj.get('map', 'Unknown Location')
        times_list = event_obj.get('times', [])

        for time_window in times_list:
            start_str = time_window.get('start')
            end_str = time_window.get('end')

            if not start_str or not end_str:
                continue

            try:
                start_time = datetime.strptime(start_str, '%H:%M').time()
                is_end_midnight_next_day = end_str == "24:00"

                if is_end_midnight_next_day:
                    is_active = start_time <= current_time_only
                else:
                    end_time_for_comparison = datetime.strptime(end_str, '%H:%M').time()
                    is_active = start_time <= current_time_only < end_time_for_comparison

                if is_active:
                    if is_end_midnight_next_day:
                        end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), datetime.min.time())
                    else:
                        end_time_for_comparison = datetime.strptime(end_str, '%H:%M').time()
                        end_datetime_naive = datetime.combine(current_date_utc, end_time_for_comparison)
                    end_datetime = end_datetime_naive.replace(tzinfo=timezone.utc)

                    time_left = end_datetime - current_time_utc
                    total_seconds = int(time_left.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_parts = []
                    if hours > 0: time_parts.append(f"{hours}ч")
                    if minutes > 0: time_parts.append(f"{minutes}м")
                    if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
                    time_left_str = " ".join(time_parts)

                    active_events.append({
                        'name': name,
                        'location': location,
                        'time_left': time_left_str,
                    })
                    continue

                # Вычисление предстоящего
                if is_end_midnight_next_day:
                    if current_time_only < start_time:
                        start_datetime_naive = datetime.combine(current_date_utc, start_time)
                    else:
                        start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)
                else:
                    end_time_for_comparison = datetime.strptime(end_str, '%H:%M').time()
                    if start_time > current_time_only:
                        start_datetime_naive = datetime.combine(current_date_utc, start_time)
                    else:
                        start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)

                start_datetime = start_datetime_naive.replace(tzinfo=timezone.utc)
                time_to_start = start_datetime - current_time_utc
                total_seconds = int(time_to_start.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_parts = []
                if hours > 0: time_parts.append(f"{hours}ч")
                if minutes > 0: time_parts.append(f"{minutes}м")
                if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
                time_to_start_str = " ".join(time_parts)

                upcoming_events.append({
                    'name': name,
                    'location': location,
                    'time_left': time_to_start_str,
                })

            except Exception as e:
                logger.error(f"Error parsing time for event {name}: {e}")
                continue

    logger.info(f"Вычисление по API (events-schedule - логика расписания) завершено: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
    return active_events, upcoming_events

# --- FastAPI с CORS ---
app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/user_events")
async def api_user_events():
    try:
        active, upcoming = get_arc_raiders_events_from_api_schedule()
        return {"active": active, "upcoming": upcoming}
    except Exception as e:
        logger.error(f"Ошибка в /api/user_events: {e}")
        return {"error": "Internal Server Error"}, 500
