-- Smart Rental Locker System SQLite Schema

-- Enable Foreign Key constraints
PRAGMA foreign_keys = ON;

-- Drop existing tables to ensure schema updates apply cleanly in dev
-- Drop statements removed to preserve data during hot reloading

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lockers Table
CREATE TABLE IF NOT EXISTS lockers (
    locker_id TEXT PRIMARY KEY,
    locker_number TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    size TEXT NOT NULL, -- 'Small', 'Medium', 'Large'
    status TEXT DEFAULT 'available' CHECK (status IN ('available', 'reserved', 'occupied', 'maintenance'))
);

-- Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    locker_id TEXT NOT NULL,
    rental_duration INTEGER NOT NULL, -- duration in minutes
    amount REAL NOT NULL,
    booking_status TEXT DEFAULT 'pending_payment' CHECK (booking_status IN ('pending_payment', 'waiting_for_door_close', 'active_rental', 'otp_generated', 'retrieval_approved', 'completed', 'expired', 'cancelled')),
    unlock_requested INTEGER DEFAULT 0, -- 1 = user requested unlock from app, 2 = retrieval unlock acknowledged
    otp TEXT, -- Legacy OTP column, kept for compatibility if needed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (locker_id) REFERENCES lockers (locker_id) ON DELETE RESTRICT
);

-- OTPs Table (New OTP Management)
CREATE TABLE IF NOT EXISTS otps (
    otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    phone_number TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0 CHECK (used IN (0, 1)),
    FOREIGN KEY (booking_id) REFERENCES bookings (booking_id) ON DELETE CASCADE
);

-- Payments Table
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_status TEXT DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid', 'failed')),
    transaction_id TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings (booking_id) ON DELETE CASCADE
);

-- Rental Logs Table (RTC Tracking)
CREATE TABLE IF NOT EXISTS rental_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_minutes INTEGER,
    FOREIGN KEY (booking_id) REFERENCES bookings (booking_id) ON DELETE CASCADE
);

-- Indexes for performance and quick retrieval
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_locker ON bookings(locker_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(booking_status);
CREATE INDEX IF NOT EXISTS idx_payments_booking ON payments(booking_id);
CREATE INDEX IF NOT EXISTS idx_rental_logs_booking ON rental_logs(booking_id);

-- Seed exactly one locker for the initial hardware setup
INSERT OR IGNORE INTO lockers (locker_id, locker_number, location, size, status)
VALUES ('LOCKER_001', '01', 'Main Lobby', 'Medium', 'available');
