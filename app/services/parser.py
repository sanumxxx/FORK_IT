import re
from datetime import datetime
import logging
from app.models.event import Event
from app import db
import pdfplumber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFParser:
    COUNTRIES = [
        'РОССИЯ', 'УЗБЕКИСТАН', 'КАЗАХСТАН', 'БЕЛАРУСЬ', 'КЫРГЫЗСТАН',
        'ТАДЖИКИСТАН', 'ТУРКМЕНИСТАН', 'АРМЕНИЯ', 'АЗЕРБАЙДЖАН', 'ГРУЗИЯ'
    ]

    SUBJECTS_RF = [
        # Республики
        "Республика Адыгея", "Республика Алтай", "Республика Башкортостан",
        "Республика Бурятия", "Республика Дагестан", "Донецкая Народная Республика",
        "Республика Ингушетия", "Кабардино-Балкарская Республика", "Республика Калмыкия",
        "Карачаево-Черкесская Республика", "Республика Карелия", "Республика Коми",
        "Луганская Народная Республика", "Республика Марий Эл", "Республика Мордовия",
        "Республика Саха (Якутия)", "Республика Северная Осетия — Алания", "Республика Татарстан",
        "Республика Тыва", "Удмуртская Республика", "Республика Хакасия", "Чеченская Республика",
        "Чувашская Республика", "Республика Крым",

        # Края
        "Алтайский край", "Забайкальский край", "Камчатский край", "Краснодарский край",
        "Красноярский край", "Пермский край", "Приморский край", "Ставропольский край",
        "Хабаровский край",

        # Области
        "Амурская область", "Архангельская область", "Астраханская область",
        "Белгородская область", "Брянская область", "Владимирская область",
        "Волгоградская область", "Вологодская область", "Воронежская область",
        "Ивановская область", "Иркутская область", "Калининградская область",
        "Калужская область", "Кемеровская область", "Кировская область",
        "Костромская область", "Курганская область", "Курская область",
        "Ленинградская область", "Липецкая область", "Магаданская область",
        "Московская область", "Мурманская область", "Нижегородская область",
        "Новгородская область", "Новосибирская область", "Омская область",
        "Оренбургская область", "Орловская область", "Пензенская область",
        "Псковская область", "Ростовская область", "Рязанская область",
        "Самарская область", "Саратовская область", "Сахалинская область",
        "Свердловская область", "Смоленская область", "Тамбовская область",
        "Тверская область", "Томская область", "Тульская область",
        "Тюменская область", "Ульяновская область", "Челябинская область",
        "Ярославская область", "Запорожская область", "Херсонская область",

        # Города федерального значения
        "Город Москва", "Город Санкт-Петербург", "Город Севастополь",

        # Автономная область
        "Еврейская автономная область",

        # Автономные округа
        "Ненецкий автономный округ", "Ханты-Мансийский автономный округ — Югра",
        "Чукотский автономный округ", "Ямало-Ненецкий автономный округ"
    ]

    @staticmethod
    def _extract_sport_type(block):
        """Извлекает вид спорта перед фразой 'Основной состав'."""
        match = re.search(r'^([А-ЯЁ\s]+)\nОсновной состав', block, re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_discipline(full_text):
        """
        Извлекает дисциплины из текста. Учитывает только последовательности с английскими символами и дефисами.
        """
        # Извлечение дисциплин в формате "F-1A, F-1B, F-1C"
        discipline_matches = re.findall(r'\b([A-Z][A-Z0-9-]+(?:,?\s?))+', full_text)
        disciplines = set()
        for match in discipline_matches:
            cleaned = match.replace(" ", "").replace(",", ", ").strip(", ")
            if re.match(r'^[A-Z0-9-]+$', cleaned):  # Убедимся, что это корректный формат
                disciplines.add(cleaned)
        return ", ".join(sorted(disciplines)) if disciplines else None

    @staticmethod
    def _parse_event_block(block, sport_type):
        """Парсит отдельный блок мероприятия."""
        try:
            logger.info(f"Parsing block:\n{block}\n{'-' * 50}")
            full_text = " ".join(line.strip() for line in block.split('\n') if line.strip())
            logger.info(f"Full text for processing: {full_text}")

            # Поиск EKP номера
            ekp_match = re.search(r'(\d{13})', full_text)
            ekp_number = ekp_match.group(1) if ekp_match else None

            # Поиск названия мероприятия
            name_match = re.search(
                r'(ЧЕМПИОНАТ|ВСЕРОССИЙСКИЕ СОРЕВНОВАНИЯ|КУБОК РОССИИ|МЕЖДУНАРОДНЫЕ СОРЕВНОВАНИЯ|[А-ЯЁ\s]{5,})',
                full_text
            )
            event_name = name_match.group(0).strip() if name_match else 'Неизвестное мероприятие'

            # Поиск всех дат
            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', full_text)
            start_date = datetime.strptime(dates[0], '%d.%m.%Y') if dates else None
            end_date = datetime.strptime(dates[1], '%d.%m.%Y') if len(dates) > 1 else None

            # Поиск возраста и группы
            age_group = None
            if len(dates) > 1:
                age_group_match = re.search(
                    fr'(женщины|мужчины|девушки|юноши|юниоры|юниорки)[^,]*(?:от\s+\d+\s+лет\s*(?:и\s*старше)?)?.*?(?={dates[1]})',
                    full_text
                )
                if age_group_match:
                    age_group = age_group_match.group(0).strip()

            # Поиск страны
            location_country = next((c for c in PDFParser.COUNTRIES if c in full_text), None)

            # Поиск региона
            location_region = next((s for s in PDFParser.SUBJECTS_RF if s.upper() in full_text.upper()), None)

            city_match = re.search(
                r'г\.\s*([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)*(?:\s+[А-ЯЁ][а-яё]+)?)', full_text
            )
            location_city = None
            if city_match:
                location_city = city_match.group(1).replace("\n", " ").strip()

            # Извлечение дисциплин
            discipline = PDFParser._extract_discipline(full_text)

            # Формирование данных мероприятия
            event_data = {
                'ekp_number': ekp_number,
                'name': event_name,
                'sport_type': sport_type,
                'discipline': discipline,
                'start_date': start_date,
                'end_date': end_date,
                'location_country': location_country,
                'location_region': location_region,
                'location_city': location_city,
                'participants_count': None,
                'age_group': age_group
            }

            logger.info(f"Parsed Event Data: {event_data}")
            return Event(**event_data)

        except Exception as e:
            logger.error(f"Error parsing block: {str(e)}\nBlock: {block}")
            return None

    @staticmethod
    def parse_pdf(file_path):
        logger.info(f"Starting to parse PDF: {file_path}")
        processed_ekp = set()
        current_sport_type = None  # Текущий вид спорта

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()

                # Разбиваем текст на блоки по номерам
                event_blocks = re.split(r'(?=\d{13})', text)

                for block in event_blocks:
                    if not block.strip():
                        continue

                    # Если вид спорта указан перед "Основной состав", обновляем текущий
                    new_sport_type = PDFParser._extract_sport_type(block)
                    if new_sport_type:
                        current_sport_type = new_sport_type
                        logger.info(f"Detected sport type: {current_sport_type}")

                    try:
                        ekp_match = re.search(r'(\d{13})', block)
                        if ekp_match and ekp_match.group(1) not in processed_ekp:
                            event = PDFParser._parse_event_block(block, current_sport_type)
                            if event:
                                PDFParser._save_event(event)
                                processed_ekp.add(ekp_match.group(1))
                                logger.info(f"Successfully processed event: {event.ekp_number}")
                    except Exception as e:
                        logger.error(f"Failed to process block: {str(e)}")

    @staticmethod
    def _save_event(event):
        try:
            existing = Event.query.filter_by(ekp_number=event.ekp_number).first()
            if not existing:
                db.session.add(event)
                db.session.commit()
                logger.info(f"✅ Saved: {event.name[:50]}...")
            else:
                logger.info(f"⚠️ Event exists: {event.ekp_number}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Database error: {str(e)}")
            raise