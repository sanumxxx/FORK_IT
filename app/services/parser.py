from app.models.event import Event
from app import db
import pdfplumber
import re
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFParser:
    @staticmethod
    def _parse_event_block(block):
        try:
            logger.info(f"Parsing block:\n{block}\n{'-' * 50}")

            # Очистка блока и извлечение строк
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            logger.info(f"Extracted lines: {lines}")

            # Объединяем все строки блока в одну строку для упрощения анализа
            full_text = " ".join(lines)
            logger.info(f"Full text for processing: {full_text}")

            # Поиск EKP номера
            ekp_match = re.search(r'(\d{13})', full_text)
            ekp_number = ekp_match.group(1) if ekp_match else None
            logger.info(f"Matched EKP: {ekp_number}")

            # Поиск названия мероприятия
            name_match = re.search(
                r'(ЧЕМПИОНАТ|ВСЕРОССИЙСКИЕ СОРЕВНОВАНИЯ|КУБОК РОССИИ(?:\s*-\s*\d+(?:-[ЫИЙ])?\s*ЭТАП)?(?:\s*СЕЗОН\s*\d{4}-\д{4}\s*ГГ\.)?|ПЕРВЕНСТВО|СПАРТАКИАДА|ТУРНИР|ИГРЫ|ОЛИМПИАДА|ФЕСТИВАЛЬ|МЕЖРЕГИОНАЛЬНЫЕ СОРЕВНОВАНИЯ)([^0-9]+)?',
                full_text
            )
            event_name = name_match.group(0).strip() if name_match else 'Неизвестное мероприятие'
            logger.info(f"Matched Event Name: {event_name}")

            # Поиск всех дат
            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', full_text)
            start_date = datetime.strptime(dates[0], '%d.%m.%Y') if dates else None
            end_date = datetime.strptime(dates[1], '%d.%m.%Y') if len(dates) > 1 else None
            logger.info(f"Matched Dates: Start: {start_date}, End: {end_date}")

            # Поиск возрастной группы между ключевыми словами и второй датой
            age_group = 'Не указано'
            if len(dates) > 1:
                # Регулярное выражение: извлечь текст, начинающийся с ключевых слов и оканчивающийся перед второй датой
                age_group_match = re.search(
                    fr'(женщины|мужчины|девушки|юноши)[^,]*(?:от\s+\d+\s+лет\s*(?:и\s*старше)?)?.*?(?={dates[1]})',
                    full_text
                )
                if age_group_match:
                    age_group = age_group_match.group(0).strip()
            logger.info(f"Matched Age Group: {age_group}")

            # Поиск региона (сразу после второй даты, капсом)
            location_region = 'Не указано'
            if len(dates) > 1:
                region_match = re.search(rf'{dates[1]}\s+([А-ЯЁ\s]+),', full_text)
                if region_match:
                    location_region = region_match.group(1).strip()
            logger.info(f"Matched Region: {location_region}")

            # Поиск города (после "г.") и удаление "КЛАСС" из города
            city_match = re.search(r'г\.\s*([^,]+)', full_text)
            location_city = city_match.group(1).strip() if city_match else 'Не указано'

            # Удаляем "КЛАСС" из конца строки, если он присутствует
            location_city = re.sub(r'\sКЛАСС.*$', '', location_city).strip()
            logger.info(f"Matched City: {location_city}")

            # Поиск классов и дисциплин
            classes = re.findall(r'КЛАСС\s+([^,\n]+)', full_text)
            disciplines = re.findall(r'дисциплин[аы]\s+([^,\n]+)', full_text)
            logger.info(f"Matched Classes: {classes}, Disciplines: {disciplines}")

            # Количество участников
            participants_match = re.search(r'\s(\d+)\s*$', full_text)
            participants_count = int(participants_match.group(1)) if participants_match else None
            logger.info(f"Matched Participants Count: {participants_count}")

            # Формирование данных мероприятия
            event_data = {
                'ekp_number': ekp_number,
                'name': event_name,
                'event_type': 'Физкультурные',
                'sport_type': 'АВИАМОДЕЛЬНЫЙ СПОРТ',
                'discipline': ', '.join(classes + disciplines) if classes or disciplines else None,
                'start_date': start_date,
                'end_date': end_date,
                'location_country': 'РОССИЯ',
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

    @staticmethod
    def parse_pdf(file_path):
        logger.info(f"Starting to parse PDF: {file_path}")
        processed_ekp = set()

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                event_blocks = re.split(r'(?=\d{13})', text)

                for block in event_blocks:
                    if not block.strip():
                        continue

                    try:
                        ekp_match = re.search(r'(\d{13})', block)
                        if ekp_match and ekp_match.group(1) not in processed_ekp:
                            event = PDFParser._parse_event_block(block)
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