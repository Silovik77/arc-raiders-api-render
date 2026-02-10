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
            return _get_events_exact(raw_events)
        elif raw_events and 'times' in raw_events[0]:
            return _get_events_schedule(raw_events)
        else:
            return [], []
    except Exception as e:
        logger.error(f"Ошибка API: {e}")
        return [], []

def _get_events_exact(raw_events):
    active_events = []
    upcoming_events = []
    current_time_utc = datetime.now(timezone.utc)

    for event_obj in raw_events:
        name = event_obj.get('name')
        location = event_obj.get('map')
        start_ms, end_ms = event_obj.get('startTime'), event_obj.get('endTime')
        if not start_ms or not end_ms: continue

        try:
            start_dt, end_dt = datetime.fromtimestamp(start_ms/1000, tz=timezone.utc), datetime.fromtimestamp(end_ms/1000, tz=timezone.utc)
            if start_dt <= current_time_utc < end_dt:
                # Вычисляем время
                time_left = end_dt - current_time_utc
                total_seconds = int(time_left.total_seconds())
                h, r = divmod(total_seconds, 3600)
                m, s = divmod(r, 60)
                t = f"{h}ч" if h else f"{m}м" if m else f"{s}с"
                active_events.append({'name': name, 'location': location, 'time_left': t})
            elif start_dt > current_time_utc:
                time_to_start = start_dt - current_time_utc
                total_seconds = int(time_to_start.total_seconds())
                h, r = divmod(total_seconds, 3600)
                m, s = divmod(r, 60)
                t = f"{h}ч" if h else f"{m}м" if m else f"{s}с"
                upcoming_events.append({'name': name, 'location': location, 'time_left': t})
        except: pass

    return active_events, upcoming_events

def _get_events_schedule(raw_events):
    active_events = []
    upcoming_events = []
    current_time_utc, current_date = datetime.now(timezone.utc), datetime.now(timezone.utc).date()

    for event_obj in raw_events:
        name = event_obj.get('name')
        location = event_obj.get('map')
        times_list = event_obj.get('times', [])
        for tw in times_list:
            start_str, end_str = tw.get('start'), tw.get('end')
            if not start_str or not end_str: continue
            try:
                start_time, end_time = datetime.strptime(start_str, '%H:%M').time(), datetime.strptime(end_str, '%H:%M').time()
                is_24 = end_str == "24:00"
                if is_24 or start_time <= end_time:
                    is_active = (is_24 and start_time <= current_time_utc.time()) or (not is_24 and start_time <= current_time_utc.time() < end_time)
                    if is_active:
                        # активное событие
                        t = "1ч"  # упрощённо для теста
                        active_events.append({'name': name, 'location': location, 'time_left': t})
                else:
                    # переходящее через полночь
                    t = "2ч"
                    active_events.append({'name': name, 'location': location, 'time_left': t})
            except: pass

    return active_events, upcoming_events

# --- FastAPI с CORS ---
app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены (для теста)
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/user_events")
async def api_user_events():
    try:
        active, upcoming = get_arc_raiders_events_from_api_schedule()
        return {"active": active, "upcoming": upcoming}
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return {"error": "Internal Server Error"}, 500

