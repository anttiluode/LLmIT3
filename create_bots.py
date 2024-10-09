import os
import sqlite3
import random
import json
import re
from openai import OpenAI
from flask_bcrypt import Bcrypt  # Import Bcrypt for password hashing

# Database for the main application
DB_NAME = "instance/llmit.db"

# Initialize OpenAI client
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Initialize Bcrypt
bcrypt = Bcrypt()

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Drop the users table if it exists (for reinitialization)
    cursor.execute('DROP TABLE IF EXISTS users')
    
    # Create the users table if it doesn't exist
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            background TEXT NOT NULL,
            goal TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'bot'  -- To differentiate between bots and humans
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"{DB_NAME} initialized successfully.")

def extract_json(response_text):
    try:
        # Use regex to find a JSON object in the response
        json_str = re.search(r'\{.*?\}', response_text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        print(f"Response text was: {response_text}")
        return None

def generate_user_profile():
    # Vary the seed randomly
    seed = random.uniform(0.310, 1.256)
    random.seed(seed)

    # Ask the AI to generate the username, background story, and goal
    prompt = (
        "Create a SINGLE (do not ramble) user profile in JSON format with the following fields:\n"
        "- username: a unique username under 10 characters\n"
        "- background: a brief background story.\n"
        "- goal: a brief statement of the user's goal.\n"
        "Respond ONLY with a valid JSON object in this format:\n"
        "{\n"
        "  \"username\": \"example\",\n"
        "  \"background\": \"This is an example background.\",\n"
        "  \"goal\": \"This is an example goal.\"\n"
        "}\n"
    )
    
    # Maintain chat history for context
    history = [
        {"role": "system", "content": "You are an intelligent assistant. Generate a user profile."},
        {"role": "user", "content": prompt}
    ]

    try:
        completion = client.chat.completions.create(
            model="unsloth/Llama-3.2-3B-Instruct-GGUF",
            messages=history,
            temperature=0.7,
            max_tokens=500,
            timeout=90  # Set a timeout directly in the API call
        )

        response_content = completion.choices[0].message.content.strip()
        print(f"AI Response: {response_content}")  # For debugging

        profile_data = extract_json(response_content)

        if profile_data and 'username' in profile_data and 'background' in profile_data and 'goal' in profile_data:
            return profile_data['username'], profile_data['background'], profile_data['goal']
        else:
            print("Failed to create a valid user profile.")
    except Exception as e:
        print(f"Error processing AI response: {e}")

    return None, None, None

def save_bot_user(username, background, goal):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Generate a random password and hash it
    random_password = os.urandom(16).hex()  # Generates a random 32-character hex string
    hashed_password = bcrypt.generate_password_hash(random_password).decode('utf-8')
    
    try:
        cursor.execute('INSERT INTO users (username, password, background, goal, user_type) VALUES (?, ?, ?, ?, "bot")', (username, hashed_password, background, goal))
        conn.commit()
        print(f"Bot user '{username}' saved to database.")
    except sqlite3.IntegrityError:
        print(f"Username '{username}' already exists in {DB_NAME}. Skipping this entry.")
    finally:
        conn.close()

if __name__ == "__main__":
    # Initialize the main database
    initialize_db()

    # Create initial users (50 users)
    for _ in range(50):  
        username, background, goal = generate_user_profile()
        if username and background and goal:
            save_bot_user(username, background, goal)
        else:
            print("User profile creation failed, moving on to the next user.")
