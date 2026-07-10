import sqlite3
import hashlib

conn = sqlite3.connect('hotel.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)''')

hashed_pw = hashlib.sha256('admin123'.encode()).hexdigest()
c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", 
          ('admin', hashed_pw, 'admin'))

conn.commit()
conn.close()
print("DB Ready! Login -> admin / admin123")
