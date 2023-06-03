from app import app
from sqlalchemy import func, text, column
from app.models import db, Visit, Movement, Waypoint, PaymentTransaction, User
import logging
import unicodedata
from logging.handlers import RotatingFileHandler
from flask import request, make_response
from datetime import datetime, timedelta
from dateutil import parser
import sqlite3
import json
import pytz
import os
import re
from bs4 import BeautifulSoup

log_file = './app/logs/app.log'

# Create a logger
logger = logging.getLogger('BackendLogs')
logger.setLevel(logging.DEBUG)

# Create a file handler with log rotation
file_handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Create a stream handler and set its level to INFO
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


@app.route('/init-db', methods=['POST'])
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    with open('app/schema.sql', 'r') as f:
        queries = f.read()
    c.executescript(queries)
    conn.commit()
    conn.close()
    return make_response('OK', 200)

@app.route('/add-user', methods=['POST'])
def add_user():
    username = request.form.to_dict().get('uname')
    user_id = insert_user(username)
    return make_response({'user_id': user_id}, 200)

def binary_search(dataset, input_time):
    left = 0
    right = len(dataset) - 1

    while left <= right:
        mid = (left + right) // 2
        mid_dataset = dataset[mid]
        start_time = parser.parse(mid_dataset.start_timestamp)
        end_time = parser.parse(mid_dataset.end_timestamp)

        if start_time <= input_time <= end_time:
            return dataset[mid]
        elif input_time < start_time:
            right = mid - 1
        else:
            left = mid + 1

    return None

@app.route('/init-google-pay-history', methods=['POST'])
def load_google_pay_history():
    g_pay_base_path = 'path/to/takeout/folder'
    logger.info('Base directory for google pay history provided as - %s' % g_pay_base_path)
    logger.info('Starting processing google pay history!')
    g_pay_activity_html = os.path.join(g_pay_base_path, 'Google Pay', 'My Activity', 'My Activity.html')
    if not os.path.isfile(g_pay_activity_html):
        logger.error('Unable to find google pay history file!')
        return make_response('File not found!', 404)

    soup = None
    with open(g_pay_activity_html) as fp:
        soup = BeautifulSoup(fp, 'html.parser')
    if not soup:
        return make_response('Could not parse google pay history', 404)

    user_id = request.form.to_dict().get('user_id')
    if not user_id:
        return make_response('User ID missing', 404)

    all_cards = soup.find_all('div', {'class':'outer-cell'})
    all_movements = db.session.query(
        Movement.start_location_lat.label('lat'),
        Movement.start_location_lng.label('lng'),
        Movement.start_timestamp,
        Movement.end_timestamp
    ).join(
        User, Movement.user_id == User.user_id
    ).filter(
        User.user_id == user_id
    ).all()
    all_visits = db.session.query(
        Visit.location_lat.label('lat'),
        Visit.location_lng.label('lng'),
        Visit.start_timestamp,
        Visit.end_timestamp
    ).join(
        User, Visit.user_id == User.user_id
    ).filter(
        User.user_id == user_id
    ).all()
    all_visits_and_movements = sorted(
        all_visits + all_movements,
        key=lambda x: parser.parse(x.start_timestamp)
    )
    payment_transactions_to_insert = []
    len_all_cards = len(all_cards)

    for index, card in enumerate(all_cards):
        logger.info('Parsing %s / %s' % (index+1, len_all_cards))
        content = unicodedata.normalize("NFKD", card.find('div', class_='content-cell').get_text(separator=' ', strip=True))
        amount = 0.0
        location_lat = None
        location_lng = None
        timestamp_utc = None

        # get amount
        try:
            amount_match = re.search(r'([\d.,]+)', content)
            amount = float(amount_match.group(1))
        except Exception as e1:
            try:
                details = card.find('div', class_='mdl-typography--caption').find('b', text='Details:').find_next_sibling('br').next_sibling.strip()
                amount_match = re.search(r'([\d.,]+)', details)
                amount = float(amount_match.group(1))
            except Exception as e2:
                continue
        
        # get transaction type
        if content.startswith(('Used ', 'Sent ', 'Paid ')):
            transaction_type = 'Sent'
        elif content.startswith('Received '):
            transaction_type = 'Received'
        elif content.startswith('Viewed '):
            continue
        else:
            logger.error('Unknown content type found %s. SKIPPING!' % content)
            continue

        # get timestamp
        timestamp_match = re.search(r'\w+\s\d{1,2},\s\d{4},\s\d{1,2}:\d{2}:\d{2}\s[APM]+\s\w{3}', content)
        if not timestamp_match:
            timestamp_match = re.search(r'\d{1,2}\s\w+\s\d{4},\s\d{2}:\d{2}:\d{2}\s\w+', content)
        timestamp_str = timestamp_match.group() if timestamp_match else None
        if timestamp_str:
            timestamp = parser.parse(timestamp_str)
            timestamp_utc = timestamp.astimezone(pytz.UTC)

        # get location
        location = card.find('a', href=lambda href: href and 'maps/search' in href)
        if location:
            location_url = location['href']
            lat_lng_match = re.search(r'query=([\d.-]+),([\d.-]+)', location_url)
            location_lat = lat_lng_match.group(1)
            location_lng = lat_lng_match.group(2)
        else:
            match = binary_search(all_visits_and_movements, timestamp_utc)
            if match:
                location_lat = match.lat
                location_lng = match.lng
        
        payment_transactions_to_insert.append({
            'transaction_type': transaction_type,
            'amount': amount,
            'location_lat': location_lat,
            'location_lng': location_lng,
            'transaction_timestamp': timestamp_utc.isoformat(),
            'user_id': user_id
        })

    if payment_transactions_to_insert:
        insert_payment_transactions(payment_transactions_to_insert)
    return make_response('OK', 200)

@app.route('/init-semantic-location-history', methods=['POST'])
def load_sematic_location_history():
    maps_hist_base_path = 'path/to/takeout/folder'
    logger.info('Base directory for semantic location history provided as - %s' % maps_hist_base_path)
    logger.info('Starting processing semantic location history!')
    scaling_factor = 1e7
    location_history_folder_path = os.path.join(maps_hist_base_path, 'Location History')
    semantic_location_history_folder_path = os.path.join(location_history_folder_path, 'Semantic Location History')
    location_history_years = os.listdir(semantic_location_history_folder_path)

    user_id = request.form.to_dict().get('user_id')
    if not user_id:
        return make_response('User ID missing', 404)
    for year in location_history_years:
        year_folder_path = os.path.join(semantic_location_history_folder_path, year)
        for month_json in os.listdir(year_folder_path):
            if month_json.endswith('.json'):
                logger.info('Processing - %s' % month_json)
                file_to_parse = os.path.join(year_folder_path, month_json)
                with open(file_to_parse, 'r') as file:
                    try:
                        data = json.load(file)
                    except Exception as e:
                        logger.error('Unable to parse %s due to %s' % (file_to_parse, e))
                        return
                    
                    timeline = data.get('timelineObjects')
                    if not timeline:
                        continue
                    for activity in timeline:
                        if 'activitySegment' in activity and is_valid_activity_segment(activity['activitySegment']):
                            start_location = activity['activitySegment']['startLocation']
                            end_location = activity['activitySegment']['endLocation']
                            duration = activity['activitySegment']['duration']
                            start_location_lat = start_location['latitudeE7'] / scaling_factor
                            start_location_lng = start_location['longitudeE7'] / scaling_factor
                            end_location_lat = end_location['latitudeE7'] / scaling_factor
                            end_location_lng = end_location['longitudeE7'] / scaling_factor
                            start_timestamp = duration['startTimestamp']
                            end_timestamp = duration['endTimestamp']
                            movement_id = insert_movement(
                                start_location_lat,
                                start_location_lng,
                                end_location_lat,
                                end_location_lng,
                                start_timestamp,
                                end_timestamp,
                                user_id
                            )
                            waypoints = activity['activitySegment'].get('waypointPath', {}).get('waypoints', [])
                            if waypoints:
                                waypoints_insert_data = []
                                for idx, waypoint in enumerate(waypoints):
                                    waypoints_insert_data.append({
                                        'movement_id': movement_id,
                                        'waypoint_order': idx + 1,
                                        'location_lat': waypoint['latE7'] / scaling_factor,
                                        'location_lng': waypoint['lngE7'] / scaling_factor,
                                        'user_id': user_id
                                    })
                                insert_waypoints(waypoints_insert_data)
                        elif 'placeVisit' in activity and is_valid_place_visit(activity['placeVisit']):
                            location_lat = activity['placeVisit']['location']['latitudeE7'] / scaling_factor
                            location_lng = activity['placeVisit']['location']['longitudeE7'] / scaling_factor
                            start_timestamp = activity['placeVisit']['duration']['startTimestamp']
                            end_timestamp = activity['placeVisit']['duration']['endTimestamp']
                            insert_visit(
                                location_lat,
                                location_lng,
                                start_timestamp,
                                end_timestamp,
                                user_id
                            )
    logger.info('Completed processing semantic location history!')
    return make_response('OK', 200)


def insert_movement(v1, v2, v3, v4, v5, v6, v7):
    movement = Movement(
        start_location_lat=v1,
        start_location_lng=v2,
        end_location_lat=v3,
        end_location_lng=v4,
        start_timestamp=v5,
        end_timestamp=v6,
        user_id=v7
    )
    db.session.add(movement)
    db.session.commit()
    return movement.movement_id

def insert_waypoints(waypoints_insert_data):
    db.session.bulk_save_objects(
        [Waypoint(**waypoint) for waypoint in waypoints_insert_data]
    )
    db.session.commit()

def insert_payment_transactions(payment_transactions):
    db.session.bulk_save_objects(
        [PaymentTransaction(**transaction) for transaction in payment_transactions]
    )
    db.session.commit()

def insert_visit(v1, v2, v3, v4, v5):
    visit = Visit(
        location_lat=v1,
        location_lng=v2,
        start_timestamp=v3,
        end_timestamp=v4,
        user_id=v5
    )
    db.session.add(visit)
    db.session.commit()
    return visit.visit_id

def insert_user(v1):
    user = User(username=v1)
    db.session.add(user)
    db.session.commit()
    return user.user_id

def is_valid_activity_segment(activity_segment):
    has_valid_start_point = bool(activity_segment.get('startLocation', {}).get('latitudeE7'))
    has_valid_end_point = bool(activity_segment.get('endLocation', {}).get('latitudeE7'))
    has_valid_duration = bool(activity_segment.get('duration', {}).get('startTimestamp'))
    return has_valid_start_point and has_valid_end_point and has_valid_duration

def is_valid_place_visit(place_visit):
    has_valid_location_lat = bool(place_visit.get('location', {}).get('latitudeE7'))
    has_valid_start_timestamp = bool(place_visit.get('duration', {}).get('startTimestamp'))
    return has_valid_location_lat and has_valid_start_timestamp

@app.route('/get-day-information', methods=['GET'])
def get_day_information():
    args = request.args
    logger.info('Attempted request to %s with arguments %s' % (request.path, args))

    date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    datetime_object = datetime.strptime(args.get('date'), date_format)
    start_timestamp = datetime_object
    end_timestamp = datetime_object + timedelta(days=1)

    user_id = args.get('userId')
    payment_type = args.get('paymentType')
    if payment_type in ('S', 'R'):
        transaction_type = ['Sent'] if payment_type == 'S' else ['Received']
    else:
        transaction_type = ['Sent', 'Received']

    movements = db.session.query(
        column('PATH').label('activity_type'),
        Movement.start_timestamp,
        Movement.end_timestamp,
        Movement.start_location_lat,
        Movement.start_location_lng,
        Movement.end_location_lat,
        Movement.end_location_lng,
        func.group_concat(Waypoint.location_lat + ',' + Waypoint.location_lng, ' ').label('waypoints')
    ).outerjoin(
        Waypoint, Movement.movement_id == Waypoint.movement_id
    ).filter(
        func.datetime(Movement.end_timestamp) >= start_timestamp,
        func.datetime(Movement.start_timestamp) < end_timestamp,
        Movement.user_id == user_id
    ).group_by(
        Movement.movement_id
    ).all()

    visits = db.session.query(
        column('VISIT').label('activity_type'),
        Visit.start_timestamp,
        Visit.end_timestamp,
        Visit.location_lat,
        Visit.location_lng    
    ).filter(
        func.datetime(Visit.end_timestamp) >= start_timestamp,
        func.datetime(Visit.start_timestamp) < end_timestamp,
        Visit.user_id == user_id
    ).all()

    payment_transactions = db.session.query(
        column('PAYMENT').label('activity_type'),
        PaymentTransaction.transaction_timestamp.label('start_timestamp'),
        PaymentTransaction.amount,
        PaymentTransaction.transaction_type,
        PaymentTransaction.location_lat,
        PaymentTransaction.location_lng   
    ).filter(
        func.datetime(PaymentTransaction.transaction_timestamp) >= start_timestamp,
        func.datetime(PaymentTransaction.transaction_timestamp) < end_timestamp,
        PaymentTransaction.user_id == user_id,
        PaymentTransaction.transaction_type.in_(transaction_type)
    ).all()

    sorted_results = sorted(
        movements + visits + payment_transactions,
        key=lambda x: parser.parse(x.start_timestamp)
    )
    return json.dumps([r._asdict() for r in sorted_results])

@app.route('/get-all-users', methods=['GET'])
def get_all_users():
    users = db.session.query(
        User.user_id,
        User.username
    ).all()
    return json.dumps([r._asdict() for r in users])
