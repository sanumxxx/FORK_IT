from app import db
from datetime import datetime, timedelta


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    ekp_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(500), nullable=False)
    event_type = db.Column(db.String(100), default='Физкультурные')
    category = db.Column(db.String(100), default='ВСЕРОССИЙСКИЕ ФИЗКУЛЬТУРНЫЕ МЕРОПРИЯТИЯ')
    sport_type = db.Column(db.String(100), nullable=False)
    discipline = db.Column(db.String(100))
    program = db.Column(db.String(100))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    location_country = db.Column(db.String(100), nullable=False)
    location_region = db.Column(db.String(100))
    location_city = db.Column(db.String(100))
    venue = db.Column(db.String(200))
    participants_count = db.Column(db.Integer)
    gender = db.Column(db.String(50))
    age_group = db.Column(db.String(100))



    def get_time_status(self):
        """Получает статус времени мероприятия"""
        now = datetime.utcnow()

        if now < self.start_date:
            # До начала события
            days_left = (self.start_date - now).days
            return {
                'status': 'upcoming',
                'days_left': days_left,
                'message': f'До начала: {days_left} дн.',
                'color': 'text-blue-600'
            }
        elif now <= self.end_date:
            # Событие идет
            days_left = (self.end_date - now).days
            return {
                'status': 'ongoing',
                'days_left': days_left,
                'message': f'До окончания: {days_left} дн.',
                'color': 'text-red-600'
            }
        else:
            # Событие завершено
            return {
                'status': 'completed',
                'days_left': 0,
                'message': 'Мероприятие завершено',
                'color': 'text-gray-600'
            }





    @classmethod
    def from_pdf_data(cls, data):
        """Create Event instance from parsed PDF data"""
        return cls(
            ekp_number=data['ekp_number'],
            name=data['name'],
            sport_type=data['sport_type'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            location_country=data['location_country'],
            location_region=data.get('location_region'),
            location_city=data.get('location_city'),
            age_group=data.get('age_group'),
            participants_count=data.get('participants_count'),
            discipline=data.get('discipline')
        )

    def to_dict(self, user_id=None):
        """
        Преобразует событие в словарь.
        Если указан user_id, добавляет информацию об избранном
        """
        time_status = self.get_time_status()

        return {
            'id': self.id,
            'ekp_number': self.ekp_number,
            'name': self.name,
            'event_type': self.event_type,
            'category': self.category,
            'sport_type': self.sport_type,
            'discipline': self.discipline,
            'program': self.program,
            'start_date': self.start_date.strftime('%d.%m.%Y'),
            'end_date': self.end_date.strftime('%d.%m.%Y'),
            'location_country': self.location_country,
            'location_region': self.location_region,
            'location_city': self.location_city,
            'venue': self.venue,
            'participants_count': self.participants_count,
            'gender': self.gender,
            'age_group': self.age_group,
            # Дополнительные поля статуса
            'time_status': time_status['status'],
            'days_left': time_status['days_left'],
            'time_message': time_status['message'],
            'time_color': time_status['color'],
            'is_favorite': self.is_favorite(user_id) if user_id else False
        }

    @staticmethod
    def get_user_favorites(user_id):
        """Получает все избранные события пользователя"""
        return Event.query.join(Favorite).filter(Favorite.user_id == user_id).all()

    @staticmethod
    def get_upcoming_events(days=7):
        """Получает предстоящие события"""
        now = datetime.utcnow()
        end_date = now + timedelta(days=days)
        return Event.query.filter(
            Event.start_date >= now,
            Event.start_date <= end_date
        ).order_by(Event.start_date).all()

    @staticmethod
    def get_ongoing_events():
        """Получает текущие события"""
        now = datetime.utcnow()
        return Event.query.filter(
            Event.start_date <= now,
            Event.end_date >= now
        ).order_by(Event.end_date).all()