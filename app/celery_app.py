# celery_app.py
from celery import Celery


def make_celery(app=None):
    celery = Celery(
        'app',
        broker='redis://localhost:6379/0',
        backend='redis://localhost:6379/0',
        include=['app.tasks']
    )

    celery.conf.update(
        enable_utc=True,
        timezone='Europe/Moscow',
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        beat_schedule={
            'check-upcoming-events': {
                'task': 'app.tasks.check_upcoming_events',
                'schedule': 3600.0,  # каждый час
            },
            'send-notifications': {
                'task': 'app.tasks.send_notifications',
                'schedule': 1800.0,  # каждые 30 минут
            },
        }
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app is not None:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery()