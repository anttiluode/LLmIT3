import os
import sqlite3
from flask_bcrypt import Bcrypt

# Database for the main application
DB_NAME = "instance/llmit.db"

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt()

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Drop tables if they exist (for reinitialization)
    cursor.execute('DROP TABLE IF EXISTS comments')
    cursor.execute('DROP TABLE IF EXISTS posts')
    cursor.execute('DROP TABLE IF EXISTS subllmits')
    cursor.execute('DROP TABLE IF EXISTS users')
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,  -- Password is mandatory and hashed
            background TEXT DEFAULT 'No background provided',  -- Allow background to be NULL, default if not provided
            goal TEXT DEFAULT 'No goal set',  -- Allow goal to be NULL, default if not provided
            user_type TEXT NOT NULL DEFAULT 'human'
        )
    ''')
    
    # Create subllmits table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subllmits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Create posts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            image_url TEXT,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            is_ai_generated BOOLEAN DEFAULT FALSE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (group_name) REFERENCES subllmits (name),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            parent_comment_id INTEGER DEFAULT NULL,  -- Allow parent_comment_id to be NULL for top-level comments
            content TEXT NOT NULL,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            is_ai_generated BOOLEAN DEFAULT FALSE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts (id),
            FOREIGN KEY (parent_comment_id) REFERENCES comments (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Insert some default subllmits for testing
    cursor.execute('''
        INSERT INTO subllmits (name) VALUES
        ('announcements'), ('general'), ('tech'), ('news')
    ''')

    # Insert a sample user for testing (username: admin, password: admin)
    hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
    cursor.execute('''
        INSERT INTO users (username, password, background, goal, user_type)
        VALUES ('admin', ?, 'Administrator account', 'Manage the platform', 'human')
    ''', (hashed_password,))

    # Insert a sample post if the posts table is empty
    cursor.execute('SELECT COUNT(*) FROM posts')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO posts (group_name, title, content, is_ai_generated, user_id)
            VALUES ('general', 'Welcome to LLMit', 'This is a sample post to get you started!', 0, 1)
        ''')

    conn.commit()
    conn.close()
    print(f"{DB_NAME} initialized successfully.")

if __name__ == "__main__":
    initialize_db()