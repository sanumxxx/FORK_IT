
from transformers import pipeline, AutoTokenizer
from app.models.event import Event
from app import db
import pdfplumber
import re
from datetime import datetime
import logging
import torch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmartParser:
    def __init__(self):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("DeepPavlov/rubert-base-cased")
            self.ner = pipeline(
                "ner",
                model="DeepPavlov/rubert-base-cased",
                tokenizer=self.tokenizer,
                aggregation_strategy="simple"
            )
            logger.info("Neural parser initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing SmartParser: {e}")
            raise

    def parse_location(self, text):
        try:
            entities = self.ner(text)
            locations = [e['word'] for e in entities if e['entity_group'] in ['LOC', 'ORG']]

            if "ПО МЕСТУ НАХОЖДЕНИЯ УЧАСТНИКОВ" in text:
                return "ПО МЕСТУ НАХОЖДЕНИЯ УЧАСТНИКОВ", "ПО МЕСТУ НАХОЖДЕНИЯ УЧАСТНИКОВ"

            if locations:
                region = city = 'Не указано'
                for loc in locations:
                    if any(x in loc for x in ['ОБЛАСТЬ', 'РЕСПУБЛИКА', 'КРАЙ', 'ОКРУГ']):
                        region = loc
                    elif 'г.' in loc or 'город' in loc.lower():
                        city = loc.replace('г.', '').strip()

                return region, city
            return 'Не указано', 'Не указано'
        except Exception as e:
            logger.error(f"Error in parse_location: {e}")
            return 'Не указано', 'Не указано'

    def parse_age_group(self, text):
        try:
            age_parts = []

            # Поиск категорий участников
            categories = re.findall(r'(женщины|мужчины|девушки|юноши)', text, re.IGNORECASE)
            if categories:
                age_parts.extend(categories)

            # Поиск возрастных ограничений
            age_match = re.search(r'от\s+(\d+)\s+лет\s*(?:и\s*старше)?', text)
            if age_match:
                age_parts.append(f"от {age_match.group(1)} лет и старше")

            return ', '.join(age_parts) if age_parts else 'Не указано'
        except Exception as e:
            logger.error(f"Error in parse_age_group: {e}")
            return 'Не указано'


class PDFParser:
    def __init__(self):
        self.smart_parser = SmartParser()

    def _parse_event_block(self, block):
        try:
            logger.info(f"\nParsing block:\n{block}\n{'-' * 50}")
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            full_text = " ".join(lines)

            # Базовый парсинг
            event_data = self._basic_parsing(full_text)

            # Улучшение результатов с помощью нейронной модели
            if self._needs_neural_enhancement(event_data):
                self._enhance_with_neural(event_data, full_text)

            logger.info(f"Parsed data: {event_data}")
            return Event(**event_data) if self._validate_results(event_data) else None

        except Exception as e:
            logger.error(f"Error parsing block: {str(e)}\nBlock: {block}")
            return None

    def _basic_parsing(self, text):
        """Базовый парсинг на основе регулярных выражений"""
        try:
            # EKP номер
            ekp_match = re.search(r'(\d{13})', text)

            # Название мероприятия
            name_match = re.search(
                r'(ЧЕМПИОНАТ|ВСЕРОССИЙСКИЕ СОРЕВНОВАНИЯ|КУБОК РОССИИ(?:\s*-\s*\d+(?:-[ЫИЙ])?\s*ЭТАП)?(?:\s*СЕЗОН\s*\d{4}-\d{4}\s*ГГ\.)?|ПЕРВЕНСТВО|СПАРТАКИАДА|ТУРНИР|ИГРЫ|ОЛИМПИАДА|ФЕСТИВАЛЬ|МЕЖРЕГИОНАЛЬНЫЕ СОРЕВНОВАНИЯ)([^0-9]+)?',
                text
            )

            # Даты
            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', text)

            # Классы и дисциплины
            classes = re.findall(r'КЛАСС\s+([^,\n]+)', text)
            disciplines = re.findall(r'дисциплин[аы]\s+([^,\n]+)', text)

            # Количество участников
            participants_match = re.search(r'\s(\d+)\s*$', text)

            # Локация
            region = city = 'Не указано'
            if "ПО МЕСТУ НАХОЖДЕНИЯ УЧАСТНИКОВ" in text:
                region = city = "ПО МЕСТУ НАХОЖДЕНИЯ УЧАСТНИКОВ"
            else:
                location_match = re.search(r'РОССИЯ\s+([^,]+),\s*([^,\n]+)', text)
                if location_match:
                    region = location_match.group(1).strip()
                    city_part = location_match.group(2).strip()
                    if 'г.' in city_part:
                        city = re.search(r'г\.\s*([^,\s]+)', city_part).group(1)
                    else:
                        city = city_part

            return {
                'ekp_number': ekp_match.group(1) if ekp_match else None,
                'name': name_match.group(0).strip() if name_match else 'Неизвестное мероприятие',
                'event_type': 'Физкультурные',
                'sport_type': 'АВИАМОДЕЛЬНЫЙ СПОРТ',
                'discipline': ', '.join(classes + disciplines) if classes or disciplines else None,
                'start_date': datetime.strptime(dates[0], '%d.%m.%Y') if dates else None,
                'end_date': datetime.strptime(dates[-1], '%d.%m.%Y') if len(dates) > 1 else None,
                'location_country': 'РОССИЯ',
                'location_region': region,
                'location_city': city,
                'participants_count': int(participants_match.group(1)) if participants_match else None,
                'age_group': self.smart_parser.parse_age_group(text)
            }
        except Exception as e:
            logger.error(f"Error in basic parsing: {e}")
            return None

    def _needs_neural_enhancement(self, event_data):
        """Проверка необходимости улучшения данных с помощью нейронной модели"""
        if not event_data:
            return True

        return any(
            event_data.get(key) in [None, 'Не указано']
            for key in ['location_region', 'location_city', 'age_group']
        )

    def _enhance_with_neural(self, event_data, text):
        """Улучшение данных с помощью нейронной модели"""
        try:
            if event_data['location_region'] == 'Не указано' or event_data['location_city'] == 'Не указано':
                neural_region, neural_city = self.smart_parser.parse_location(text)
                if event_data['location_region'] == 'Не указано':
                    event_data['location_region'] = neural_region
                if event_data['location_city'] == 'Не указано':
                    event_data['location_city'] = neural_city

            if event_data['age_group'] == 'Не указано':
                event_data['age_group'] = self.smart_parser.parse_age_group(text)

        except Exception as e:
            logger.error(f"Error in neural enhancement: {e}")

    def _validate_results(self, event_data):
        """Валидация результатов парсинга"""
        required_fields = ['ekp_number', 'name', 'start_date', 'end_date']
        return all(event_data.get(field) for field in required_fields)

    def parse_pdf(self, file_path):
        """Основной метод парсинга PDF"""
        logger.info(f"Starting to parse PDF: {file_path}")
        processed_ekp = set()

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.info(f"Processing page {page_num}")
                    text = page.extract_text()

                    # Пропускаем заголовок документа
                    if "ЕДИНОГО КАЛЕНДАРНОГО ПЛАНА" in text:
                        text = text[text.find("АВИАМОДЕЛЬНЫЙ СПОРТ"):]

                    event_blocks = re.split(r'(?=\d{13})', text)

                    for block in event_blocks:
                        if not block.strip() or len(block) < 50:  # Пропускаем короткие блоки
                            continue

                        # Пропускаем технические заголовки
                        if any(header in block for header in [
                            "ЕДИНОГО КАЛЕНДАРНОГО ПЛАНА",
                            "Основной состав",
                            "Наименование спортивного мероприятия",
                            "Сроки проведения",
                            "Место проведения"
                        ]):
                            continue

                        try:
                            event = self._parse_event_block(block)
                            if event and event.ekp_number and event.ekp_number not in processed_ekp:
                                self._save_event(event)
                                processed_ekp.add(event.ekp_number)
                                logger.info(f"Successfully processed event: {event.ekp_number}")
                        except Exception as e:
                            logger.error(f"Error processing block: {str(e)}")

        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            raise

    @staticmethod
    def _save_event(event):
        """Сохранение события в базу данных"""
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


