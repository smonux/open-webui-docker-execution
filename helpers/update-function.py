import sqlite3
from datetime import datetime
import argparse
import time

# Set up argument parsing
parser = argparse.ArgumentParser(description="Update a function's content in the SQLite database.")
parser.add_argument('--name', required=True, help="Name of the function to update")
parser.add_argument('--file', required=True, help="Path to the file containing the new content")
parser.add_argument('--db', required=True, help="Path to the SQLite database")
args = parser.parse_args()

# Path to the SQLite database
db_path = args.db

# Path to the file whose content you want to update in the database
file_path = args.file

# Name of the function to update
function_name = args.name

# Read the content of the file
with open(file_path, 'r') as file:
    file_content = file.read()

# Connect to the SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Update the content and updated_at columns in the functions table
update_query = """
UPDATE function
SET content = ?, updated_at = ?
WHERE name = ?  -- Use the name column to identify the row to update
"""

# Get the current Unix timestamp
current_time = int(time.time())
cursor.execute(update_query, (file_content, current_time, function_name))

# Commit the transaction
conn.commit()

# Close the connection
conn.close()

print(f"Update for function '{function_name}' successful!")
