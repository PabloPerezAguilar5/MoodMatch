#MoodMatch 🎭

MoodMatch is a web app that analyzes your emotions and recommends music and books based on how you feel.

## Features

- AI-powered emotion analysis (Hugging Face)
- Music recommendations via Spotify
- Book recommendations via Google Books
- Modern, responsive interface

## Requirements

- Python 3.8+
- Django 3.2+
- Hugging Face account
- Spotify developer account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/youruser/moodmatch.git
cd moodmatch
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file with your API credentials.

4. Run the migrations:
```bash
python manage.py migrate
```

5. Start the server:
```bash
python manage.py runserver
```

## Usage

1. Visit `http://localhost:8000` in your browser
2. Type how you feel in the text box
3. Click "Analyze Emotion"
4. Get personalized music and book recommendations!

## Contribute

Contributions are welcome. Please open an issue first to discuss changes you'd like to make.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.