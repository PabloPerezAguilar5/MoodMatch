from django.db import models
from django.utils import timezone

# Create your models here.

class EmotionalEntry(models.Model):
    texto = models.TextField(max_length=500, verbose_name="Texto del usuario")
    emocion_primaria = models.CharField(max_length=50, verbose_name="Emoción primaria")
    emocion_secundaria = models.CharField(max_length=50, verbose_name="Emoción secundaria")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha de registro")
    respuesta_correcta = models.BooleanField(default=True, verbose_name="¿Respuesta correcta?")
    notas_revision = models.TextField(blank=True, null=True, verbose_name="Notas de revisión")
    
    class Meta:
        verbose_name = "Entrada Emocional"
        verbose_name_plural = "Entradas Emocionales"
        ordering = ['-fecha']  # Ordenar por fecha descendente
    
    def __str__(self):
        return f"{self.emocion_primaria} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"

    @classmethod
    def get_tendencia(cls):
        """Analiza la tendencia emocional basada en las últimas entradas"""
        ultimas_entradas = cls.objects.filter(respuesta_correcta=True).order_by('-fecha')[:5]
        if not ultimas_entradas:
            return None
            
        # Mapeo de emociones a valores numéricos (simplificado)
        emocion_valor = {
            'joy': 1,
            'love': 1,
            'surprise': 0.5,
            'neutral': 0,
            'fear': -0.5,
            'anger': -1,
            'sadness': -1,
            'disgust': -1
        }
        
        valores = [emocion_valor.get(entrada.emocion_primaria.lower(), 0) for entrada in ultimas_entradas]
        if len(valores) >= 2:
            tendencia = sum(valores[:3]) / len(valores[:3]) - sum(valores[-2:]) / len(valores[-2:])
            if tendencia > 0.3:
                return "mejorando"
            elif tendencia < -0.3:
                return "empeorando"
        return "estable"

    @classmethod
    def get_stats_data(cls, days=30):
        """Obtiene datos para el gráfico de tendencias"""
        from django.db.models import Count
        from django.db.models.functions import TruncDay
        
        # Obtener entradas de los últimos X días
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        # Agrupar por día y emoción
        stats = cls.objects.filter(
            fecha__range=(start_date, end_date),
            respuesta_correcta=True
        ).annotate(
            dia=TruncDay('fecha')
        ).values('dia', 'emocion_primaria').annotate(
            total=Count('id')
        ).order_by('dia', 'emocion_primaria')
        
        return stats
