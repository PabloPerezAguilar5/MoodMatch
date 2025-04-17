from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from .models import EmotionalEntry
from django.db.models import Count
from django.utils import timezone
import json
from django.core.serializers.json import DjangoJSONEncoder

@admin.register(EmotionalEntry)
class EmotionalEntryAdmin(admin.ModelAdmin):
    list_display = ('texto', 'emocion_primaria', 'emocion_secundaria', 'fecha', 'respuesta_correcta')
    list_filter = ('emocion_primaria', 'emocion_secundaria', 'fecha', 'respuesta_correcta')
    search_fields = ('texto', 'emocion_primaria', 'emocion_secundaria', 'notas_revision')
    date_hierarchy = 'fecha'
    readonly_fields = ('fecha',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='emotional-stats'),
        ]
        return custom_urls + urls

    def stats_view(self, request):
        # Obtener estadísticas
        stats_data = EmotionalEntry.get_stats_data()
        
        # Preparar datos para el gráfico
        dates = sorted(set(stat['dia'].strftime('%Y-%m-%d') for stat in stats_data))
        emotions = sorted(set(stat['emocion_primaria'] for stat in stats_data))
        
        # Crear diccionario de datos
        data_dict = {date: {emotion: 0 for emotion in emotions} for date in dates}
        for stat in stats_data:
            date = stat['dia'].strftime('%Y-%m-%d')
            data_dict[date][stat['emocion_primaria']] = stat['total']
        
        context = {
            'stats_data': stats_data,
            'dates_json': json.dumps(dates, cls=DjangoJSONEncoder),
            'emotions_json': json.dumps(list(emotions), cls=DjangoJSONEncoder),
            'data_json': json.dumps(data_dict, cls=DjangoJSONEncoder),
            'title': 'Estadísticas Emocionales',
            'opts': self.model._meta,
        }
        
        return TemplateResponse(request, 'admin/emotional_stats.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_stats_link'] = True
        return super().changelist_view(request, extra_context=extra_context)
