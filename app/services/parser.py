import re
from datetime import datetime
import logging
from app.models.event import Event
from app import db
import pdfplumber

ENABLE_DEBUG_LOGGING = False  # Измените на True чтобы включить подробное логирование

# Настройка логирования в зависимости от константы
logging.basicConfig(
    level=logging.DEBUG if ENABLE_DEBUG_LOGGING else logging.WARNING
)
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

    def __init__(self):
        self.total_pages = 0
        self.current_page = 0
        self.processed_events = 0
        self.total_events = 0
        self.status_callback = None

    def set_status_callback(self, callback):
        """Установка callback-функции для отправки статуса"""
        self.status_callback = callback

    def update_status(self, message, progress):
        """Обновление статуса обработки"""
        if self.status_callback:
            self.status_callback({
                'message': message,
                'progress': progress,
                'current_page': self.current_page,
                'total_pages': self.total_pages,
                'processed_events': self.processed_events,
                'total_events': self.total_events
            })

    @staticmethod
    def _extract_sport_type(block):
        """Извлекает вид спорта перед фразой 'Основной состав'."""
        match = re.search(r'^([А-ЯЁ\s]+)\nОсновной состав', block, re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_discipline(full_text):
        """Извлекает дисциплины из текста."""
        discipline_matches = re.findall(r'\b([A-Z][A-Z0-9-]+(?:,?\s?))+', full_text)
        disciplines = set()
        for match in discipline_matches:
            cleaned = match.replace(" ", "").replace(",", ", ").strip(", ")
            if re.match(r'^[A-Z0-9-]+$', cleaned):
                disciplines.add(cleaned)
        return ", ".join(sorted(disciplines)) if disciplines else None

    def _parse_event_block(self, block, sport_type, page):
        try:
            logger.info(f"Parsing block:\n{block}\n{'-' * 50}")

            # Извлекаем слова со стилями
            words = page.extract_words(
                extra_attrs=['fontname', 'size'],
                keep_blank_chars=True
            )

            # Debug: печатаем все слова с их характеристиками
            for word in words:
                logger.debug(f"Word: {word['text']}, Size: {word['size']}, Font: {word['fontname']}")

            # Поиск EKP номера
            ekp_match = re.search(r'(\d{13})', block)
            ekp_number = ekp_match.group(1) if ekp_match else None

            # Поиск названия мероприятия
            event_name = None
            if ekp_number:
                ekp_pos = block.find(ekp_number) + len(ekp_number)
                name_parts = []

                for word in words:
                    # Проверяем размер шрифта (8) и что текст написан капсом
                    if abs(float(word['size']) - 8.0) < 0.1 and word[
                        'text'].isupper():  # используем 0.1 для погрешности
                        text = word['text'].strip()
                        if text and not text.isdigit():  # игнорируем числа
                            name_parts.append(text)
                    elif name_parts:  # если уже начали собирать название и встретили другой текст
                        # Проверяем, не является ли следующее слово частью названия
                        next_text = word['text'].strip()
                        if not (abs(float(word['size']) - 8.0) < 0.1 and next_text.isupper()):
                            break

                if name_parts:
                    event_name = ' '.join(name_parts)
                    logger.info(f"Found name by font size: {event_name}")

            # Если не нашли название по размеру шрифта, используем запасной вариант
            if not event_name:
                name_match = re.search(
                    r'(ЧЕМПИОНАТ|ВСЕРОССИЙСКИЕ СОРЕВНОВАНИЯ|КУБОК РОССИИ|МЕЖДУНАРОДНЫЕ СОРЕВНОВАНИЯ|ПЕРВЕНСТВО|[А-ЯЁ\s]{5,})',
                    block
                )
                event_name = name_match.group(0).strip() if name_match else 'Неизвестное мероприятие'
                logger.info(f"Found name by regex: {event_name}")

            full_text = " ".join(line.strip() for line in block.split('\n') if line.strip())
            # Поиск дат
            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', full_text)
            start_date = datetime.strptime(dates[0], '%d.%m.%Y') if dates else None
            end_date = datetime.strptime(dates[1], '%d.%m.%Y') if len(dates) > 1 else None

            # Поиск страны и количества участников
            country_participants_match = re.search(
                r'(РОССИЯ|УЗБЕКИСТАН|КАЗАХСТАН|БЕЛАРУСЬ|КЫРГЫЗСТАН|ТАДЖИКИСТАН|ТУРКМЕНИСТАН|АРМЕНИЯ|АЗЕРБАЙДЖАН|ГРУЗИЯ)\s+(\d+)\s+',
                full_text)
            location_country = country_participants_match.group(1) if country_participants_match else None
            participants_count = int(country_participants_match.group(2)) if country_participants_match else None

            # Поиск региона
            location_region = next((s for s in self.SUBJECTS_RF if s.upper() in full_text.upper()), None)

            # Поиск города
            city_match = re.search(
                r'г\.\s*([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)*(?:\s+[А-ЯЁ][а-яё]+)?)', full_text
            )
            location_city = None
            if city_match:
                location_city = city_match.group(1).replace("\n", " ").strip()

            # Поиск возрастной группы
            age_group = None
            if country_participants_match:
                age_group_match = re.search(
                    fr'{country_participants_match.group(2)}\s+(.*?)(?={dates[1]}|$)',
                    full_text
                )
                if age_group_match:
                    age_group = age_group_match.group(1).strip()

            # Извлечение дисциплин
            discipline = self._extract_discipline(full_text)

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
                'participants_count': participants_count,
                'age_group': age_group
            }

            logger.info(f"Parsed Event Data: {event_data}")
            return Event(**event_data)

        except Exception as e:
            logger.error(f"Error parsing block: {str(e)}\nBlock: {block}")
            return None

    def _save_event(self, event):
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

    def parse_pdf(self, file_path):
        """Основной метод парсинга PDF файла"""
        logger.info(f"Starting to parse PDF: {file_path}")
        processed_ekp = set()
        current_sport_type = None
        pdf = None

        try:
            pdf = pdfplumber.open(file_path)
            self.total_pages = len(pdf.pages)
            self.update_status(f"Всего страниц: {self.total_pages}", 0)

            # Обработка страниц
            for page_num, page in enumerate(pdf.pages, 1):
                self.current_page = page_num
                text = page.extract_text()
                event_blocks = re.split(r'(?=\d{13})', text)

                # Вычисляем прогресс
                progress = (page_num / self.total_pages) * 100
                self.update_status(
                    f"Обработка страницы {page_num} из {self.total_pages}",
                    progress
                )

                for block in event_blocks:
                    if not block.strip():
                        continue

                    new_sport_type = self._extract_sport_type(block)
                    if new_sport_type:
                        current_sport_type = new_sport_type

                    try:
                        ekp_match = re.search(r'(\d{13})', block)
                        if ekp_match and ekp_match.group(1) not in processed_ekp:
                            event = self._parse_event_block(block, current_sport_type, page)
                            if event:
                                self._save_event(event)
                                processed_ekp.add(ekp_match.group(1))
                                self.processed_events += 1

                    except Exception as e:
                        logger.error(f"Failed to process block: {str(e)}")

            self.update_status(
                f"Обработка завершена. Обработано {self.processed_events} событий",
                100
            )

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            self.update_status(f"Ошибка обработки файла: {str(e)}", 0)
            raise

        finally:
            if pdf:
                pdf.close()