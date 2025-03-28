# Entry point for WSGI servers like Gunicorn

from app import app, db, setup_mqtt # Import necessary components from your main app file

# It's crucial to initialize MQTT and DB *after* potential forking by Gunicorn workers
# Gunicorn's post_fork hook is a good place, but for simplicity,
# we rely on Flask's @before_first_request or explicit calls in __main__ for dev.
# For Gunicorn, you might configure hooks in its config file instead.

# Example Gunicorn command:
# gunicorn --bind 0.0.0.0:5000 wsgi:app

# If you need explicit init here (less common for Flask apps structured this way):
# with app.app_context():
#     try:
#         db.create_all()
#         print("WSGI: Database tables checked/created.")
#     except Exception as e:
#         print(f"WSGI CRITICAL: Failed to create database tables: {e}")
#     setup_mqtt(app)
#     print("WSGI: MQTT client setup initiated.")

if __name__ == "__main__":
    # This allows running the development server via `python wsgi.py`
    # Ensure necessary initializations happen
    print("Running development server via wsgi.py...")
    with app.app_context():
         try:
              db.create_all()
              print("WSGI Dev: Database tables checked/created.")
         except Exception as e:
              print(f"WSGI Dev CRITICAL: Failed to create database tables: {e}")
         setup_mqtt(app)
         print("WSGI Dev: MQTT client setup initiated.")

    app.run(host='0.0.0.0', port=5000, debug=True)
