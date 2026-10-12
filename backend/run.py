import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Not 5000: macOS uses it for AirPlay Receiver.
    app.run(debug=True, port=int(os.environ.get("PORT", "5001")))
