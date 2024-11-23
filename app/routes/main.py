from flask import Blueprint, render_template, request, jsonify, current_app, json, send_file, flash, redirect, url_for, abort
from werkzeug.utils import secure_filename
from app.models.event import Event
from app.services.parser import PDFParser
from app import db, cache
import os
from datetime import datetime
import logging
from flask import Response, stream_with_context
import json
import queue
import threading
import secrets
from flask_login import login_user, logout_user, login_required, current_user
import time

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

status_queue = queue.Queue()




@bp.route('/')
@cache.cached(timeout=300)
def index():
    return render_template('index.html', csp_nonce=lambda: secrets.token_hex(16))







@bp.route('/events')
def get_events():
    try:
        sport_type = request.args.get('sport_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        region = request.args.get('region')
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Количество записей на страницу

        query = Event.query

        if sport_type:
            query = query.filter_by(sport_type=sport_type)
        if region:
            query = query.filter_by(location_region=region)
        if start_date:
            date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Event.start_date >= date_obj)
        if end_date:
            date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Event.end_date <= date_obj)

        paginated_events = query.paginate(page=page, per_page=per_page)

        return jsonify({
            'events': [event.to_dict() for event in paginated_events.items],
            'has_next': paginated_events.has_next,
            'total': paginated_events.total
        })

    except Exception as e:
        logger.error(f"Error in get_events: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/regions', methods=['GET'])
def get_unique_regions():
    try:
        # Извлекаем уникальные значения `location_region` из базы данных
        unique_regions = db.session.query(Event.location_region).distinct().all()
        regions = [region[0] for region in unique_regions if region[0] is not None]  # Убираем None
        return jsonify(regions), 200
    except Exception as e:
        logger.error(f"Error in get_unique_regions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/process-status')
def process_status():
    def generate():
        try:
            total_events = 0
            processed_events = 0

            def progress_callback(event):
                nonlocal processed_events
                processed_events += 1
                progress = (processed_events / total_events) * 100 if total_events > 0 else 0

                # Отправляем информацию о прогрессе
                yield f"data: {json.dumps({'type': 'progress', 'percent': progress, 'status': 'Обработка мероприятий...', 'message': f'Обработано {processed_events} из {total_events}'})}\n\n"

                # Отправляем информацию о новом мероприятии
                yield f"data: {json.dumps({'type': 'event', 'event': event.to_dict()})}\n\n"

            # Здесь должна быть логика обработки PDF
            # При каждом новом обработанном мероприятии вызывается progress_callback

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@bp.route('/sports', methods=['GET'])
def get_unique_sports():
    try:
        # Извлекаем уникальные значения `sport_type` из базы данных
        unique_sports = db.session.query(Event.sport_type).distinct().all()
        sports = [sport[0] for sport in unique_sports if sport[0] is not None]  # Убираем None
        return jsonify(sports), 200
    except Exception as e:
        logger.error(f"Error in get_unique_sports: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        app = current_app._get_current_object()  # Получаем объект приложения

        try:
            file.save(filepath)

            # Создаем парсер
            parser = PDFParser()

            # Устанавливаем callback для обновления статуса
            def status_callback(status):
                status_queue.put(status)

            parser.set_status_callback(status_callback)

            # Запускаем парсинг в отдельном потоке
            def parse_with_app():
                with app.app_context():  # Создаем контекст приложения внутри потока
                    try:
                        parser.parse_pdf(filepath)  # Теперь не нужно передавать app
                    finally:
                        # Даем файлу время закрыться
                        import time
                        time.sleep(1)

                        # Пробуем удалить файл несколько раз
                        for _ in range(3):
                            try:
                                if os.path.exists(filepath):
                                    os.remove(filepath)
                                    break
                            except PermissionError:
                                time.sleep(1)

            threading.Thread(target=parse_with_app).start()

            return jsonify({'message': 'Начата обработка файла', 'status': 'processing'}), 200

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid file type'}), 400







@bp.route('/parse-status')
def parse_status():
    def generate():
        try:
            while True:
                try:
                    status = status_queue.get(timeout=30)
                    logger.info(f"Sending status update: {status}")  # Добавим лог
                    yield f"data: {json.dumps(status)}\n\n"

                    if status['progress'] == 100:
                        break

                except queue.Empty:
                    logger.warning("Status queue timeout")  # Добавим лог
                    break

        except Exception as e:
            logger.error(f"Error in parse_status: {str(e)}")  # Добавим лог
            status = {
                'message': f'Ошибка: {str(e)}',
                'progress': 0,
                'current_page': 0,
                'total_pages': 0,
                'processed_events': 0,
                'total_events': 0
            }
            yield f"data: {json.dumps(status)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']