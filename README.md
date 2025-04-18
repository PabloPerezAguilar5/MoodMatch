# MoodMatch 

MoodMatch is a web application that analyzes your emotions and recommends music and books based on how you feel. It uses artificial intelligence to understand your emotions and provide personalized recommendations.

## Features ✨

- **Emotion Analysis**: 
  - Uses Hugging Face's "pysentimiento/robertuito-emotion-analysis" model
  - Fallback system with Spanish keyword analysis
  - Detects primary and secondary emotions

- **Music Recommendations**:
  - Spotify API integration
  - Emotion-based intelligent search
  - Song previews when available

- **Book Recommendations**:
  - Google Books API integration
  - Books related to your emotional state
  - Preference for Spanish content

- **Psychological Advice**:
  - Personalized advice based on your emotion
  - Motivational phrases
  - Emotional pattern tracking

## Technologies 🛠️

- **Backend**: Django 3.2+
- **APIs**: 
  - Hugging Face (Emotion Analysis)
  - Spotify Web API (Music)
  - Google Books API (Books)
- **Main Dependencies**:
  - django>=3.2.0
  - transformers>=4.30.0
  - torch>=2.0.0
  - spotipy>=2.23.0
  - requests>=2.31.0
  - python-dotenv>=1.0.0
  - google-api-python-client>=2.100.0
  - django-environ>=0.11.2
  - django-crispy-forms>=2.0
  - gunicorn>=21.2.0
  - whitenoise>=6.5.0
  - psycopg2-binary>=2.9.9

## Installation 🚀

1. Clone the repository:
```bash
git clone https://github.com/yourusername/moodmatch.git
cd moodmatch
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
- Create a `.env` file based on `.env.example`
- Add your credentials:
  ```
  # Spotify API Credentials
  SPOTIPY_CLIENT_ID=your_client_id
  SPOTIPY_CLIENT_SECRET=your_client_secret
  
  # Hugging Face Token (optional)
  HF_TOKEN=your_token
  ```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start the server:
```bash
python manage.py runserver
```

## Usage 💡

1. Access `http://localhost:8000`
2. Type how you feel in the text box
3. The system will analyze your emotions and provide you with:
   - The detected emotion
   - A recommended song
   - A suggested book
   - Personalized psychological advice

## Supported Emotions 🎭

- **Joy** (alegría)
- **Sadness** (tristeza)
- **Anger** (enojo)
- **Fear** (miedo)
- **Love** (amor)

## Contributing 🤝

Contributions are welcome. Please:

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

