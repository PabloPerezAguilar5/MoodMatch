from django.shortcuts import render
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import os
import logging
import random
import time
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException
from .models import EmotionalEntry
from django.db.models import Count

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logger = logging.getLogger(__name__)

def validate_text(text):
    if not text or len(text.strip()) == 0:
        raise ValidationError("El texto no puede estar vacío")
    if len(text) > 500:
        raise ValidationError("El texto es demasiado largo (máximo 500 caracteres)")
    return text.strip()

def get_emotion(text, max_retries=3):
    """
    Intenta obtener la emoción usando la API de HuggingFace.
    Si falla, usa el análisis de fallback.
    """
    # Temporalmente forzamos el uso del fallback para debuggear
    logger.info("Usando análisis fallback para debug")
    return fallback_emotion_analysis(text)

def fallback_emotion_analysis(text):
    """Análisis simple de emociones basado en palabras clave cuando la API falla"""
    text = text.lower().strip()
    logger.info(f"Analizando texto: '{text}'")

    # Diccionario simplificado para debug
    emotion_keywords = {
        "joy": [
            "feliz", "contento", "contenta", "alegre", "bien",
            "genial", "fantástico", "excelente"
        ],
        "sadness": [
            "triste", "mal", "deprimido", "deprimida"
        ],
        "anger": [
            "enojado", "enojada", "molesto", "molesta", "furioso", "furiosa"
        ],
        "love": [
            "enamorado", "enamorada", "amor", "quiero", "adoro"
        ],
        "fear": [
            "miedo", "asustado", "asustada", "preocupado", "preocupada"
        ]
    }

    # Contar coincidencias de palabras clave
    emotion_scores = {emotion: 0 for emotion in emotion_keywords}
    
    # Analizar palabra por palabra
    words = text.split()
    logger.info(f"Palabras encontradas: {words}")

    for word in words:
        logger.info(f"Analizando palabra: '{word}'")
        for emotion, keywords in emotion_keywords.items():
            if word in keywords:
                emotion_scores[emotion] += 2
                logger.info(f"Coincidencia exacta encontrada para {emotion}: {word}")
            elif any(keyword in word for keyword in keywords):
                emotion_scores[emotion] += 1
                logger.info(f"Coincidencia parcial encontrada para {emotion}: {word}")

    logger.info(f"Puntajes finales: {emotion_scores}")

    # Si no hay coincidencias
    if all(score == 0 for score in emotion_scores.values()):
        logger.info("No se encontraron coincidencias, usando valor por defecto")
        return "joy", "love"

    # Obtener las dos emociones con más coincidencias
    sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_emotions[0][0]
    secondary = sorted_emotions[1][0] if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 0 else primary

    logger.info(f"Emociones detectadas: primaria={primary}, secundaria={secondary}")
    return primary, secondary

def get_spotify_recommendations(emotion, secondary_emotion, sp):
    # Lista predefinida de géneros válidos de Spotify (verificados y seguros)
    SPOTIFY_GENRES = [
        "pop", "rock", "hip-hop", "latin"
    ]

    # Mapeo simple de emociones a configuraciones musicales
    emotion_music_mapping = {
        "joy": {
            "genres": ["pop", "latin"],
            "min_valence": 0.6,
            "min_energy": 0.6,
            "target_tempo": 120
        },
        "sadness": {
            "genres": ["rock"],
            "max_valence": 0.4,
            "max_energy": 0.4,
            "target_tempo": 80
        },
        "anger": {
            "genres": ["rock", "hip-hop"],
            "min_energy": 0.7,
            "target_tempo": 130
        },
        "fear": {
            "genres": ["rock"],
            "max_valence": 0.3,
            "target_instrumentalness": 0.6
        },
        "love": {
            "genres": ["pop", "latin"],
            "target_valence": 0.7,
            "target_acousticness": 0.5
        }
    }

    try:
        # Obtener configuración para la emoción primaria
        config = emotion_music_mapping.get(emotion, emotion_music_mapping["joy"])
        
        # Filtrar géneros válidos
        valid_genres = [g for g in config["genres"] if g in SPOTIFY_GENRES]
        
        if not valid_genres:
            valid_genres = ["pop"]  # Género seguro por defecto
        
        # Limitar a 2 géneros máximo
        seed_genres = valid_genres[:2]
        
        # Parámetros base de recomendación
        params = {
            "seed_genres": seed_genres,
            "limit": 10  # Pedimos más para tener más opciones
        }
        
        # Agregar parámetros de audio si existen
        audio_features = {k: v for k, v in config.items() 
                         if k not in ["genres"] and isinstance(v, (int, float))}
        params.update(audio_features)

        logger.info(f"Solicitando recomendaciones con parámetros: {params}")
        
        try:
            # Intentar obtener recomendaciones
            recommendations = sp.recommendations(**params)
            if recommendations and recommendations['tracks']:
                tracks = recommendations['tracks']
                # Filtrar tracks que tengan preview_url
                valid_tracks = [t for t in tracks if t.get('preview_url')]
                if valid_tracks:
                    track = random.choice(valid_tracks)
                else:
                    track = random.choice(tracks)
            else:
                raise ValueError("No se encontraron recomendaciones")
                
        except (SpotifyException, ValueError) as e:
            # Si falla la recomendación, intentar búsqueda simple
            logger.warning(f"Error en recomendaciones: {str(e)}, intentando búsqueda simple")
            mood_terms = {
                "joy": ["happy", "upbeat", "fun"],
                "sadness": ["sad", "melancholic", "slow"],
                "anger": ["powerful", "intense", "strong"],
                "fear": ["calm", "peaceful", "quiet"],
                "love": ["romantic", "love song", "sweet"]
            }
            
            search_term = random.choice(mood_terms.get(emotion, mood_terms["joy"]))
            search_genre = random.choice(seed_genres)
            
            try:
                result = sp.search(q=f"genre:{search_genre} {search_term}", 
                                 type="track", limit=10)
                
                if not result['tracks']['items']:
                    # Si no hay resultados con género, intentar sin género
                    result = sp.search(q=search_term, type="track", limit=10)
                    
                if not result['tracks']['items']:
                    raise ValueError("No se encontraron canciones")
                
                # Intentar encontrar una canción con preview_url
                valid_tracks = [t for t in result['tracks']['items'] if t.get('preview_url')]
                track = random.choice(valid_tracks) if valid_tracks else random.choice(result['tracks']['items'][:5])
                
            except Exception as e:
                logger.error(f"Error en búsqueda simple: {str(e)}")
                raise

        return {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "url": track["external_urls"]["spotify"],
            "preview_url": track.get("preview_url"),
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo recomendación de Spotify: {str(e)}")
        raise

def get_book_recommendation(emotion, secondary_emotion):
    # Mapeo más detallado de emociones a términos de búsqueda de libros
    emotion_book_mapping = {
        "joy": ["inspirational", "humor", "feel-good", "comedy", "uplifting"],
        "sadness": ["moving", "emotional", "literary fiction", "drama", "poetry"],
        "anger": ["empowerment", "social justice", "revolution", "transformation"],
        "fear": ["psychological thriller", "mystery", "suspense", "gothic"],
        "surprise": ["magical realism", "science fiction", "fantasy", "adventure"],
        "disgust": ["dystopian", "dark fiction", "critique", "satire"],
        "love": ["romance", "relationships", "contemporary love", "passion"]
    }

    # Combinar términos de búsqueda de ambas emociones
    primary_terms = emotion_book_mapping.get(emotion, ["fiction"])
    secondary_terms = emotion_book_mapping.get(secondary_emotion, ["fiction"])
    
    # Elegir términos al azar de ambas listas
    search_terms = random.sample(primary_terms, 1) + random.sample(secondary_terms, 1)
    search_query = " ".join(search_terms)

    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": search_query,
                "maxResults": 5,
                "langRestrict": "es",  # preferir libros en español
                "orderBy": "relevance"
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("items"):
            raise ValueError("No se encontraron libros")

        # Elegir un libro al azar entre los primeros resultados
        book = random.choice(data["items"])["volumeInfo"]
        return {
            "title": book.get("title", "Sin título"),
            "author": ", ".join(book.get("authors", ["Autor desconocido"])),
            "url": book.get("infoLink", "#"),
            "description": book.get("description", "")[:200] + "..." if book.get("description") else ""
        }
    except Exception as e:
        logger.error(f"Error obteniendo recomendación de libro: {str(e)}")
        raise

def get_psychological_advice(emotion):
    """Obtiene consejos psicológicos y frases motivacionales según la emoción."""
    advice_mapping = {
        "joy": {
            "phrase": "¡Qué maravilloso es sentirse así! Comparte tu alegría con otros, la felicidad se multiplica cuando se comparte.",
            "advice": "Aprovecha este momento positivo para establecer nuevas metas. Escribe en un diario estos momentos felices para recordarlos después. Usa esta energía positiva para ayudar a otros."
        },
        "sadness": {
            "phrase": "Es normal sentirse triste a veces. Recuerda que cada día es una nueva oportunidad y esto también pasará.",
            "advice": "Permítete sentir tus emociones sin juzgarlas. Habla con alguien de confianza sobre cómo te sientes. Realiza actividades que antes te gustaban, aunque ahora no tengas muchas ganas. Si la tristeza persiste, considera hablar con un profesional de la salud mental."
        },
        "anger": {
            "phrase": "La ira es una señal de que algo necesita cambiar. Usa esa energía de manera constructiva.",
            "advice": "Respira profundamente durante 5 minutos. Sal a caminar para despejar tu mente. Escribe lo que sientes para procesarlo mejor. Pregúntate: ¿Qué necesito realmente en este momento?"
        },
        "fear": {
            "phrase": "El miedo es una respuesta natural que nos protege, pero no dejes que te paralice.",
            "advice": "Identifica qué es exactamente lo que te asusta. Divide los grandes miedos en pasos más pequeños y manejables. Practica técnicas de relajación y mindfulness. Recuerda momentos en los que superaste tus miedos."
        },
        "love": {
            "phrase": "El amor es una de las emociones más poderosas. Cultívalo tanto hacia otros como hacia ti mismo.",
            "advice": "Expresa tu afecto a las personas que quieres. Practica el autocuidado y el amor propio. Mantén un equilibrio entre dar y recibir amor. Cultiva relaciones saludables y recíprocas."
        },
        "surprise": {
            "phrase": "La sorpresa nos mantiene presentes y nos recuerda que la vida está llena de posibilidades.",
            "advice": "Mantén una mente abierta ante lo inesperado. Usa esta energía para explorar nuevas posibilidades. Aprende de las situaciones inesperadas. Cultiva la curiosidad en tu vida diaria."
        },
        "disgust": {
            "phrase": "El rechazo nos ayuda a establecer límites. Escucha lo que tu mente y cuerpo te dicen.",
            "advice": "Identifica qué está causando este sentimiento. Establece límites saludables si es necesario. Busca alternativas que te hagan sentir mejor. No te sientas culpable por establecer límites."
        }
    }

    return advice_mapping.get(emotion, advice_mapping["joy"])

def get_emotional_trend_message(emotion):
    """Genera un mensaje basado en el historial emocional"""
    ultimas_entradas = EmotionalEntry.objects.all().order_by('-fecha')[:5]
    
    if not ultimas_entradas:
        return None
        
    # Contar frecuencia de emociones
    emociones_frecuentes = EmotionalEntry.objects.values('emocion_primaria')\
        .annotate(total=Count('emocion_primaria'))\
        .order_by('-total')[:1]
    
    emocion_mas_frecuente = emociones_frecuentes[0]['emocion_primaria'] if emociones_frecuentes else None
    
    # Obtener tendencia
    tendencia = EmotionalEntry.get_tendencia()
    
    # Generar mensaje personalizado
    mensajes = {
        "mejorando": {
            "joy": "¡Excelente! Tu estado de ánimo está mejorando. ¡Sigue así!",
            "sadness": "Aunque hoy te sientas triste, veo que has tenido mejores momentos recientemente.",
            "default": "Veo una tendencia positiva en tu estado de ánimo. ¡Eso es genial!"
        },
        "empeorando": {
            "joy": "¡Qué bueno verte feliz hoy! Es un cambio positivo respecto a días anteriores.",
            "sadness": "He notado que has estado pasando por momentos difíciles. ¿Has considerado hablar con alguien al respecto?",
            "default": "Últimamente has experimentado emociones más intensas. Recuerda que estoy aquí para escucharte."
        },
        "estable": {
            "joy": "¡Sigues manteniendo un estado de ánimo positivo!",
            "sadness": "Has estado experimentando tristeza por un tiempo. Recuerda que buscar ayuda es un signo de fortaleza.",
            "default": "Tu estado emocional se ha mantenido estable."
        }
    }
    
    if tendencia:
        return mensajes[tendencia].get(emotion, mensajes[tendencia]["default"])
    return None

def mood_match(request):
    # Inicializar contexto vacío para peticiones GET
    if request.method == "GET":
        return render(request, "core/moodmatch.html", {})
    
    # Procesar peticiones POST
    context = {}
    
    if request.method == "POST":
        texto = request.POST.get("texto", "").strip()
        
        try:
            texto = validate_text(texto)
            try:
                primary_emotion, secondary_emotion = get_emotion(texto)
                context["is_fallback"] = False
            except requests.exceptions.RequestException:
                primary_emotion, secondary_emotion = fallback_emotion_analysis(texto)
                context["is_fallback"] = True

            # Guardar entrada emocional
            EmotionalEntry.objects.create(
                texto=texto,
                emocion_primaria=primary_emotion,
                emocion_secundaria=secondary_emotion
            )

            # Obtener mensaje de tendencia
            trend_message = get_emotional_trend_message(primary_emotion)
            if trend_message:
                context["trend_message"] = trend_message

            # Obtener consejos psicológicos
            psychological_advice = get_psychological_advice(primary_emotion)
            context["advice"] = psychological_advice

            # SPOTIFY
            spotify_id = os.getenv("SPOTIPY_CLIENT_ID")
            spotify_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
            
            if not all([spotify_id, spotify_secret]):
                raise ValueError("Credenciales de Spotify no configuradas")

            sp = Spotify(auth_manager=SpotifyClientCredentials(
                client_id=spotify_id,
                client_secret=spotify_secret
            ))
            
            context["song"] = get_spotify_recommendations(primary_emotion, secondary_emotion, sp)
            context["book"] = get_book_recommendation(primary_emotion, secondary_emotion)
            
            context["emotion"] = primary_emotion
            context["secondary_emotion"] = secondary_emotion
            context["success"] = True

        except ValidationError as e:
            logger.warning(f"Error de validación: {str(e)}")
            context["error"] = str(e)
        except ValueError as e:
            logger.error(f"Error de configuración: {str(e)}")
            context["error"] = f"Error de configuración: {str(e)}"
        except Exception as e:
            logger.exception("Error inesperado")
            context["error"] = "Lo sentimos, ha ocurrido un error inesperado"

    return render(request, "core/moodmatch.html", context)
        