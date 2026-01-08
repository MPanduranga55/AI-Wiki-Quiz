"""
Migration script to change raw_html column from TEXT to LONGTEXT.
Run this once after updating models.py to fix the "Data too long" error.
"""
import os
import dotenv
from sqlalchemy import create_engine, text

# Load .env file
dotenv.load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL must be set in .env file")

if not database_url.startswith("mysql"):
    raise RuntimeError("This migration is for MySQL only")

engine = create_engine(database_url)

print("Migrating raw_html column to LONGTEXT...")

with engine.connect() as conn:
    # Check if column exists and is not already LONGTEXT
    result = conn.execute(text("""
        SELECT COLUMN_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'quizzes' 
        AND COLUMN_NAME = 'raw_html'
    """))
    
    row = result.fetchone()
    if row:
        current_type = row[0].upper()
        if 'LONGTEXT' in current_type:
            print("Column is already LONGTEXT. No migration needed.")
        else:
            print(f"Current type: {current_type}. Changing to LONGTEXT...")
            conn.execute(text("ALTER TABLE quizzes MODIFY COLUMN raw_html LONGTEXT"))
            conn.commit()
            print("Migration completed successfully!")
    else:
        print("Column 'raw_html' not found. Table may need to be created.")
        print("Restart the FastAPI server to create tables with the new schema.")

print("Done.")

