from app import db
from datetime import datetime


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
            age_group=data.get('age_group')
        )

    def to_dict(self):
        return {
            'id': self.id,
            'ekp_number': self.ekp_number,
            'name': self.name,
            'event_type': self.event_type,
            'category': self.category,
            'sport_type': self.sport_type,
            'start_date': self.start_date.strftime('%d.%m.%Y'),
            'end_date': self.end_date.strftime('%d.%m.%Y'),
            'location': {
                'country': self.location_country,
                'region': self.location_region,
                'city': self.location_city,
                'venue': self.venue
            },
            'age_group': self.age_group
        }