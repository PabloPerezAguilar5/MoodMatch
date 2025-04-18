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
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logger = logging.getLogger(__name__)

# Inicializar el modelo de análisis de emociones
try:
    logger.info("Cargando modelo de Hugging Face...")
    model_name = "pysentimiento/robertuito-emotion-analysis"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    emotion_classifier = pipeline(
        "text-classification",
        model=model,
        tokenizer=tokenizer,
        device="cpu"  # Forzar CPU para evitar errores de CUDA
    )
    logger.info("Modelo de Hugging Face cargado correctamente")
except Exception as e:
    logger.error(f"Error al cargar el modelo de Hugging Face: {str(e)}", exc_info=True)
    emotion_classifier = None

def validate_text(text):
    if not text or len(text.strip()) == 0:
        raise ValidationError("El texto no puede estar vacío")
    if len(text) > 500:
        raise ValidationError("El texto es demasiado largo (máximo 500 caracteres)")
    return text.strip()

def get_emotion(text, max_retries=3):
    """
    Intenta obtener la emoción usando Hugging Face.
    Si falla, usa el análisis de fallback.
    """
    logger.info("="*50)
    logger.info(f"INICIO análisis de texto: '{text}'")
    
    if emotion_classifier is None:
        logger.warning("Modelo de Hugging Face no disponible, usando fallback")
        return fallback_emotion_analysis(text)

    try:
        # Obtener predicciones del modelo
        logger.info("Intentando usar Hugging Face...")
        prediction = emotion_classifier(text)
        logger.info(f"ÉXITO - Predicción de Hugging Face: {prediction}")

        # Mapear las etiquetas del modelo a nuestras categorías
        emotion_mapping = {
            "joy": "joy",
            "sadness": "sadness",
            "anger": "anger",
            "fear": "fear",
            "surprise": "joy",  # Mapeamos surprise a joy por defecto
            "others": "joy"     # Cualquier otra emoción la mapeamos a joy
        }

        # Obtener la emoción principal
        primary_label = prediction[0]['label']
        score = prediction[0]['score']
        logger.info(f"Emoción detectada: {primary_label} con confianza: {score:.2f}")
        
        primary_emotion = emotion_mapping.get(primary_label, "joy")
        
        # Para la emoción secundaria, usamos el fallback
        _, secondary_emotion = fallback_emotion_analysis(text)

        logger.info(f"Emociones FINALES - HF primaria: {primary_emotion}, secundaria: {secondary_emotion}")
        logger.info("="*50)
        return primary_emotion, secondary_emotion

    except Exception as e:
        logger.error(f"ERROR al usar Hugging Face: {str(e)}", exc_info=True)
        logger.info("Cayendo al análisis fallback")
        return fallback_emotion_analysis(text)

def fallback_emotion_analysis(text):
    """Análisis simple de emociones basado en palabras clave"""
    text = text.lower().strip()
    logger.info(f"INICIO análisis fallback para: '{text}'")

    # Diccionario simplificado de emociones y palabras clave
    emotion_keywords = {
        "joy": [
            "feliz", "contento", "contenta", "alegre", "genial",
            "fantástico", "fantástica", "excelente", "bien", "bueno", "buena"
        ],
        "sadness": [
            "triste", "mal", "deprimido", "deprimida", "dolor",
            "pena", "melancolía", "melancolico", "melancolica"
        ],
        "anger": [
            "enojado", "enojada", "molesto", "molesta", "furioso",
            "furiosa", "rabia", "ira", "bronca"
        ],
        "fear": [
            "miedo", "asustado", "asustada", "temor", "terror",
            "preocupado", "preocupada", "ansioso", "ansiosa"
        ],
        "love": [
            "amor", "enamorado", "enamorada", "quiero", "adoro",
            "cariño", "amo"
        ]
    }

    # Contar coincidencias
    emotion_scores = {emotion: 0 for emotion in emotion_keywords}
    words = text.split()
    
    for word in words:
        logger.info(f"Analizando palabra: '{word}'")
        for emotion, keywords in emotion_keywords.items():
            if word in keywords:
                emotion_scores[emotion] += 1
                logger.info(f"¡Coincidencia encontrada!: {word} -> {emotion}")

    logger.info(f"Puntajes finales del fallback: {emotion_scores}")

    # Si no hay coincidencias, usar joy como default
    if all(score == 0 for score in emotion_scores.values()):
        logger.info("No se encontraron coincidencias, usando 'joy' por defecto")
        return "joy", "love"

    # Obtener las dos emociones con más coincidencias
    sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_emotions[0][0]
    secondary = sorted_emotions[1][0] if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 0 else primary

    logger.info(f"Emociones FINALES del fallback: primaria={primary}, secundaria={secondary}")
    return primary, secondary

def get_spotify_recommendations(emotion, secondary_emotion, sp):
    """
    Obtiene recomendaciones musicales de Spotify basadas en la emoción.
    """
    try:
        # Mapeo simple de emociones a términos de búsqueda
        search_terms = {
            "joy": "happy dance pop",
            "sadness": "sad acoustic",
            "anger": "rock metal",
            "fear": "ambient chill",
            "love": "romantic love songs"
        }

        # Usar búsqueda simple en lugar de recomendaciones
        search_term = search_terms.get(emotion, "pop")
        logger.info(f"Buscando canciones con término: {search_term}")
        
        try:
            result = sp.search(q=search_term, type="track", limit=10)
            if result and result['tracks']['items']:
                tracks = result['tracks']['items']
                # Preferir tracks con preview_url
                valid_tracks = [t for t in tracks if t.get('preview_url')]
                track = random.choice(valid_tracks if valid_tracks else tracks)
                return {
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "url": track["external_urls"]["spotify"],
                    "preview_url": track.get("preview_url"),
                }
        except Exception as e:
            logger.error(f"Error en búsqueda de Spotify: {e}")

    except Exception as e:
        logger.error(f"Error general de Spotify: {e}")
    
    # Si algo falla, retornar respuesta por defecto
    return {
        "name": "No se pudo obtener canción",
        "artist": "Intente más tarde",
        "url": "#",
        "preview_url": None
    }

def get_book_recommendation(emotion, secondary_emotion):
    """
    Por ahora retornamos un libro hardcodeado mientras arreglamos la API.
    """
    return {
        "title": "Temporalmente no disponible",
        "author": "Intente más tarde",
        "url": "#",
        "description": "El servicio de recomendación de libros está temporalmente no disponible."
    }

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
        