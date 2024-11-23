from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.models.event import Event
from app.services.parser import PDFParser
from app import db, cache
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)


@bp.route('/')
@cache.cached(timeout=300)
def index():
    return render_template('index.html')


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
        file.save(filepath)

        try:
            parser = PDFParser()
            parser.parse_pdf(filepath)
            return jsonify({'message': 'PDF processed successfully'}), 200
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    return jsonify({'error': 'Invalid file type'}), 400


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']