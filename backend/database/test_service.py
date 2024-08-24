import mysql.connector

# Replace placeholders with your actual values
db_config = {
    'user': 'admin',
    'password': 'adeyinka',
    'host': 'genaiq:us-central1:genaiq',
    'database': 'genaiq',
}

try:
    # Connect to the database
    conn = mysql.connector.connect(**db_config)

    # Create a cursor object
    cursor = conn.cursor()

    # Execute the SHOW DATABASES command
    cursor.execute("SHOW DATABASES")

    # Fetch results
    databases = cursor.fetchall()

    # Print the list of databases
    print("Available Databases:")
    for db in databases:
        print(db[0])

    # Close the cursor and connection
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Error: {err}")
