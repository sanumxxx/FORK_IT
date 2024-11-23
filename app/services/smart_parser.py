
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import torch
import logging

logger = logging.getLogger(__name__)


class SmartParser:
    def __init__(self):
        try:
            # Инициализация модели для русского языка
            self.tokenizer = AutoTokenizer.from_pretrained("DeepPavlov/rubert-base-cased")
            self.ner = pipeline(
                "ner",
                model="DeepPavlov/rubert-base-cased",
                tokenizer=self.tokenizer,
                aggregation_strategy="simple"
            )
        except Exception as e:
            logger.error(f"Error initializing SmartParser: {e}")
            raise

    def parse_location(self, text):
        try:
            entities = self.ner(text)
            locations = [e['word'] for e in entities if e['entity_group'] in ['LOC', 'ORG']]

            if locations:
                # Пытаемся определить регион и город
                region = city = 'Не указано'
                for loc in locations:
                    if any(x in loc for x in ['ОБЛАСТЬ', 'РЕСПУБЛИКА', 'КРАЙ']):
                        region = loc
                    elif 'г.' in loc or 'город' in loc.lower():
                        city = loc.replace('г.', '').strip()

                return region, city
            return 'Не указано', 'Не указано'
        except Exception as e:
            logger.error(f"Error in parse_location: {e}")
            return 'Не указано', 'Не указано'

    def parse_event_type(self, text):
        try:
            entities = self.ner(text)
            events = [e['word'] for e in entities if e['entity_group'] == 'EVENT']
            return events[0] if events else 'Неизвестное мероприятие'
        except Exception as e:
            logger.error(f"Error in parse_event_type: {e}")
            return 'Неизвестное мероприятие'

    def parse_age_group(self, text):
        try:
            # Используем модель для определения возрастных групп
            results = self.ner(text)
            age_parts = []

            # Ищем упоминания возраста и категорий
            for entity in results:
                if entity['entity_group'] == 'PER':
                    word = entity['word'].lower()
                    if any(x in word for x in ['женщины', 'мужчины', 'девушки', 'юноши']):
                        age_parts.append(word)

            return ', '.join(age_parts) if age_parts else 'Не указано'
        except Exception as e:
            logger.error(f"Error in parse_age_group: {e}")
            return 'Не указано'


