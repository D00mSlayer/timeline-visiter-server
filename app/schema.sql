CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT
);

CREATE TABLE IF NOT EXISTS movement (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    start_location_lat REAL,
    start_location_lng REAL,
    end_location_lat REAL,
    end_location_lng REAL,
    start_timestamp TEXT,
    end_timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES user (user_id)
);

CREATE TABLE IF NOT EXISTS waypoint (
    waypoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    movement_id INTEGER,
    waypoint_order INTEGER,
    location_lat REAL,
    location_lng REAL,
    FOREIGN KEY (user_id) REFERENCES user (user_id),
    FOREIGN KEY (movement_id) REFERENCES movement (movement_id)
);

CREATE TABLE IF NOT EXISTS visit (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    location_lat REAL,
    location_lng REAL,
    start_timestamp TEXT,
    end_timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES user (user_id)
);

CREATE TABLE IF NOT EXISTS payment_transaction (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    transaction_type TEXT,
    amount REAL,
    location_lat REAL,
    location_lng REAL,
    transaction_timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES user (user_id)
);
