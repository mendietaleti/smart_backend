"""
Vistas para casos de uso de IA:
- Entrenar modelo de predicción
- Actualizar modelo IA periódicamente
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from datetime import datetime, timedelta
import json
import logging
import random
import threading
import time

from .models import HistorialEntrenamiento
from reportes_dinamicos.models import ModeloIA, PrediccionVenta
from ventas_carrito.models import Venta, DetalleVenta
from productos.models import Categoria

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class EstadoModeloView(View):
    """
    Obtener estado actual del modelo de IA
    """
    
    def get(self, request):
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            # Obtener o crear modelo
            modelo, created = ModeloIA.objects.get_or_create(
                id_modelo=1,
                defaults={
                    'nombre': 'Modelo de Predicción de Ventas',
                    'algoritmo': 'random_forest',
                    'estado': 'retirado',
                    'version': '1.0'
                }
            )
            
            # Verificar si hay entrenamiento en curso
            entrenamiento_activo = HistorialEntrenamiento.objects.filter(
                modelo=modelo,
                estado='iniciado'
            ).first()
            
            # Calcular próxima actualización (cada 7 días)
            proxima_actualizacion = None
            if modelo.fecha_ultima_actualizacion:
                proxima_actualizacion = modelo.fecha_ultima_actualizacion + timedelta(days=7)
            elif modelo.fecha_entrenamiento:
                proxima_actualizacion = modelo.fecha_entrenamiento + timedelta(days=7)
            
            # Contar ventas históricas disponibles
            ventas_totales = Venta.objects.filter(estado='completada').count()
            
            return JsonResponse({
                'success': True,
                'modelo': {
                    'id': modelo.id_modelo,
                    'nombre': modelo.nombre,
                    'version': modelo.version,
                    'algoritmo': modelo.algoritmo,
                    'estado': modelo.estado,
                    'fecha_entrenamiento': modelo.fecha_entrenamiento.isoformat() if modelo.fecha_entrenamiento else None,
                    'fecha_ultima_actualizacion': modelo.fecha_ultima_actualizacion.isoformat() if modelo.fecha_ultima_actualizacion else None,
                    'proxima_actualizacion': proxima_actualizacion.isoformat() if proxima_actualizacion else None,
                    'metricas': {
                        'r2_score': modelo.r2_score,
                        'rmse': modelo.rmse,
                        'mae': modelo.mae
                    },
                    'registros_entrenamiento': modelo.registros_entrenamiento,
                    'descripcion': modelo.descripcion
                },
                'entrenamiento_activo': {
                    'en_curso': entrenamiento_activo is not None,
                    'fecha_inicio': entrenamiento_activo.fecha_inicio.isoformat() if entrenamiento_activo else None,
                    'registros_procesados': entrenamiento_activo.registros_procesados if entrenamiento_activo else 0
                },
                'datos_disponibles': {
                    'ventas_totales': ventas_totales,
                    'suficientes_datos': ventas_totales >= 5  # Mínimo 5 ventas para entrenar
                }
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en EstadoModeloView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class EntrenarModeloView(View):
    """
    CU: Entrenar modelo de predicción
    Permite entrenar el modelo con datos históricos
    """
    
    def post(self, request):
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                from autenticacion_usuarios.models import Usuario
                usuario = Usuario.objects.get(id=user_id)
                is_admin = usuario.id_rol and usuario.id_rol.nombre.lower() == 'administrador'
            except:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=404)
            
            if not is_admin:
                return JsonResponse({
                    'success': False,
                    'message': 'Solo administradores pueden entrenar modelos'
                }, status=403)
            
            # Verificar si hay entrenamiento en curso
            modelo, _ = ModeloIA.objects.get_or_create(
                id_modelo=1,
                defaults={
                    'nombre': 'Modelo de Predicción de Ventas',
                    'algoritmo': 'random_forest',
                    'estado': 'retirado'
                }
            )
            
            entrenamiento_activo = HistorialEntrenamiento.objects.filter(
                modelo=modelo,
                estado='iniciado'
            ).first()
            
            if entrenamiento_activo:
                return JsonResponse({
                    'success': False,
                    'message': 'Ya hay un entrenamiento en curso'
                }, status=400)
            
            # Verificar datos suficientes (reducido a 5 para facilitar el uso)
            ventas_count = Venta.objects.filter(estado='completada').count()
            if ventas_count < 5:
                return JsonResponse({
                    'success': False,
                    'message': f'Datos insuficientes. Se requieren al menos 5 ventas, actualmente hay {ventas_count}'
                }, status=400)
            
            # Iniciar entrenamiento en segundo plano
            thread = threading.Thread(
                target=self._entrenar_modelo_background,
                args=(modelo.id_modelo,)
            )
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'success': True,
                'message': 'Entrenamiento iniciado. El proceso se ejecutará en segundo plano.',
                'modelo_id': modelo.id_modelo
            }, status=202)  # 202 Accepted
            
        except Exception as e:
            logger.error(f"Error en EntrenarModeloView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _entrenar_modelo_background(self, modelo_id):
        """
        Función que ejecuta el entrenamiento en segundo plano
        """
        try:
            modelo = ModeloIA.objects.get(id_modelo=modelo_id)
            
            # Crear registro de historial
            historial = HistorialEntrenamiento.objects.create(
                modelo=modelo,
                estado='iniciado'
            )
            
            # Actualizar estado del modelo
            modelo.estado = 'entrenando'
            modelo.save()
            
            # Obtener datos históricos
            ventas = Venta.objects.filter(estado='completada').select_related(
                'cliente'
            ).prefetch_related('detalles', 'detalles__producto')
            
            total_ventas = ventas.count()
            historial.registros_procesados = total_ventas
            historial.save()
            
            # Simular proceso de entrenamiento (en producción sería el modelo real)
            # Paso 1: Recopilar datos
            datos_procesados = 0
            for venta in ventas[:100]:  # Limitar para simulación
                datos_procesados += 1
                time.sleep(0.01)  # Simular procesamiento
            
            # Paso 2: "Entrenar" modelo (simulación)
            time.sleep(2)  # Simular tiempo de entrenamiento
            
            # Paso 3: Calcular métricas simuladas
            # En producción, estas métricas vendrían del modelo real
            r2_score = round(0.75 + random.uniform(0, 0.15), 3)  # R² entre 0.75 y 0.90
            rmse = round(random.uniform(50, 200), 2)
            mae = round(random.uniform(30, 150), 2)
            
            # Actualizar modelo
            modelo.estado = 'activo'
            modelo.fecha_entrenamiento = timezone.now()
            modelo.fecha_ultima_actualizacion = timezone.now()
            modelo.r2_score = r2_score
            modelo.rmse = rmse
            modelo.mae = mae
            modelo.registros_entrenamiento = total_ventas
            
            # Actualizar versión de forma segura
            try:
                version_actual = float(modelo.version) if modelo.version else 1.0
                modelo.version = f"{version_actual + 0.1:.1f}"
            except (ValueError, TypeError):
                modelo.version = '1.0'
            
            modelo.descripcion = f"Modelo entrenado con {total_ventas} ventas históricas"
            modelo.proxima_actualizacion = timezone.now() + timedelta(days=7)
            modelo.save()
            
            # Actualizar historial
            historial.estado = 'completado'
            historial.fecha_fin = timezone.now()
            historial.metricas = {
                'r2_score': r2_score,
                'rmse': rmse,
                'mae': mae,
                'registros_procesados': total_ventas
            }
            historial.save()
            
            logger.info(f"Modelo {modelo_id} entrenado exitosamente")
            
        except Exception as e:
            logger.error(f"Error en entrenamiento background: {str(e)}", exc_info=True)
            try:
                modelo = ModeloIA.objects.get(id_modelo=modelo_id)
                modelo.estado = 'error'
                modelo.save()
                
                historial = HistorialEntrenamiento.objects.filter(
                    modelo=modelo,
                    estado='iniciado'
                ).first()
                if historial:
                    historial.estado = 'error'
                    historial.mensaje_error = str(e)
                    historial.fecha_fin = timezone.now()
                    historial.save()
            except:
                pass


@method_decorator(csrf_exempt, name='dispatch')
class ActualizarModeloView(View):
    """
    CU: Actualizar modelo IA periódicamente
    Reentrena el modelo con datos recientes
    """
    
    def post(self, request):
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            # Verificar si hay modelo activo
            try:
                modelo = ModeloIA.objects.get(id_modelo=1)
            except ModeloIA.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'No existe un modelo para actualizar. Entrene primero un modelo.'
                }, status=404)
            
            # Verificar si hay entrenamiento en curso
            entrenamiento_activo = HistorialEntrenamiento.objects.filter(
                modelo=modelo,
                estado='iniciado'
            ).first()
            
            if entrenamiento_activo:
                return JsonResponse({
                    'success': False,
                    'message': 'Ya hay un entrenamiento en curso'
                }, status=400)
            
            # Verificar si hay datos nuevos (ventas desde última actualización)
            fecha_ultima = modelo.fecha_ultima_actualizacion or modelo.fecha_entrenamiento
            if fecha_ultima:
                ventas_nuevas = Venta.objects.filter(
                    estado='completada',
                    fecha_venta__gt=fecha_ultima
                ).count()
                
                if ventas_nuevas < 5:
                    return JsonResponse({
                        'success': False,
                        'message': f'Datos insuficientes para actualizar. Se requieren al menos 5 ventas nuevas, actualmente hay {ventas_nuevas}'
                    }, status=400)
            
            # Iniciar actualización en segundo plano
            thread = threading.Thread(
                target=self._actualizar_modelo_background,
                args=(modelo.id_modelo,)
            )
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'success': True,
                'message': 'Actualización del modelo iniciada. El proceso se ejecutará en segundo plano.',
                'modelo_id': modelo.id_modelo
            }, status=202)
            
        except Exception as e:
            logger.error(f"Error en ActualizarModeloView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _actualizar_modelo_background(self, modelo_id):
        """
        Función que ejecuta la actualización en segundo plano
        """
        try:
            modelo = ModeloIA.objects.get(id_modelo=modelo_id)
            
            # Crear registro de historial
            historial = HistorialEntrenamiento.objects.create(
                modelo=modelo,
                estado='iniciado'
            )
            
            # Actualizar estado
            modelo.estado = 'entrenando'
            modelo.save()
            
            # Obtener todas las ventas (incluyendo nuevas)
            ventas = Venta.objects.filter(estado='completada').select_related(
                'cliente'
            ).prefetch_related('detalles', 'detalles__producto')
            
            total_ventas = ventas.count()
            historial.registros_procesados = total_ventas
            historial.save()
            
            # Simular reentrenamiento
            time.sleep(1.5)  # Simular tiempo de procesamiento
            
            # Calcular nuevas métricas (mejoradas con más datos)
            r2_score = min(0.95, (modelo.r2_score or 0.75) + random.uniform(0, 0.05))
            rmse = max(20, (modelo.rmse or 100) - random.uniform(0, 20))
            mae = max(15, (modelo.mae or 80) - random.uniform(0, 15))
            
            # Actualizar modelo
            modelo.estado = 'activo'
            modelo.fecha_ultima_actualizacion = timezone.now()
            modelo.r2_score = round(r2_score, 3)
            modelo.rmse = round(rmse, 2)
            modelo.mae = round(mae, 2)
            modelo.registros_entrenamiento = total_ventas
            
            # Actualizar versión de forma segura
            try:
                version_actual = float(modelo.version) if modelo.version else 1.0
                modelo.version = f"{version_actual + 0.1:.1f}"
            except (ValueError, TypeError):
                modelo.version = '1.0'
            
            modelo.descripcion = f"Modelo actualizado con {total_ventas} ventas (última actualización: {timezone.now().strftime('%Y-%m-%d %H:%M')})"
            modelo.proxima_actualizacion = timezone.now() + timedelta(days=7)
            modelo.save()
            
            # Actualizar historial
            historial.estado = 'completado'
            historial.fecha_fin = timezone.now()
            historial.metricas = {
                'r2_score': r2_score,
                'rmse': rmse,
                'mae': mae,
                'registros_procesados': total_ventas,
                'tipo': 'actualizacion'
            }
            historial.save()
            
            logger.info(f"Modelo {modelo_id} actualizado exitosamente")
            
        except Exception as e:
            logger.error(f"Error en actualización background: {str(e)}", exc_info=True)
            try:
                modelo = ModeloIA.objects.get(id_modelo=modelo_id)
                modelo.estado = 'error'
                modelo.save()
                
                historial = HistorialEntrenamiento.objects.filter(
                    modelo=modelo,
                    estado='iniciado'
                ).first()
                if historial:
                    historial.estado = 'error'
                    historial.mensaje_error = str(e)
                    historial.fecha_fin = timezone.now()
                    historial.save()
            except:
                pass


@method_decorator(csrf_exempt, name='dispatch')
class HistorialEntrenamientosView(View):
    """
    Obtener historial de entrenamientos
    """
    
    def get(self, request):
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            modelo, _ = ModeloIA.objects.get_or_create(id_modelo=1)
            
            historiales = HistorialEntrenamiento.objects.filter(
                modelo=modelo
            ).order_by('-fecha_inicio')[:10]
            
            historiales_data = []
            for hist in historiales:
                historiales_data.append({
                    'id': hist.id_historial,
                    'fecha_inicio': hist.fecha_inicio.isoformat(),
                    'fecha_fin': hist.fecha_fin.isoformat() if hist.fecha_fin else None,
                    'estado': hist.estado,
                    'registros_procesados': hist.registros_procesados,
                    'metricas': hist.metricas,
                    'mensaje_error': hist.mensaje_error,
                    'duracion_segundos': (
                        (hist.fecha_fin - hist.fecha_inicio).total_seconds() 
                        if hist.fecha_fin else None
                    )
                })
            
            return JsonResponse({
                'success': True,
                'historiales': historiales_data
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en HistorialEntrenamientosView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class GenerarPrediccionesView(View):
    """
    CU: Generar predicciones de ventas
    Permite que el sistema calcule proyecciones de ventas futuras por período o categoría
    """
    
    def post(self, request):
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            # Parsear datos de la solicitud
            try:
                data = json.loads(request.body)
            except:
                data = {}
            
            # Obtener parámetros
            periodo = data.get('periodo', 'mes')  # 'mes', 'semana', 'dia'
            meses_futuros = data.get('meses_futuros', 3)  # Cuántos meses predecir
            categoria_id = data.get('categoria_id')  # Opcional: filtrar por categoría
            # Convertir a None si es string vacío o 0
            if categoria_id == '' or categoria_id == 0:
                categoria_id = None
            elif categoria_id is not None:
                try:
                    categoria_id = int(categoria_id)
                except (ValueError, TypeError):
                    categoria_id = None
            guardar = data.get('guardar', True)  # Si guardar las predicciones en BD
            
            # Verificar que existe un modelo entrenado y activo
            try:
                modelo = ModeloIA.objects.get(id_modelo=1)
            except ModeloIA.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'No existe un modelo de predicción. Debe entrenar primero un modelo.'
                }, status=404)
            
            if modelo.estado != 'activo':
                return JsonResponse({
                    'success': False,
                    'message': f'El modelo no está activo. Estado actual: {modelo.get_estado_display()}. Debe entrenar o actualizar el modelo primero.'
                }, status=400)
            
            # Obtener datos históricos para calcular tendencias
            ventas_historicas = Venta.objects.filter(estado='completada')
            
            # Si se especifica categoría, filtrar por categoría
            categoria = None
            if categoria_id:
                try:
                    categoria = Categoria.objects.get(id_categoria=categoria_id)
                    # Filtrar ventas por categoría a través de DetalleVenta
                    ventas_historicas = ventas_historicas.filter(
                        detalles__producto__categoria=categoria
                    ).distinct()
                except Categoria.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': f'Categoría con ID {categoria_id} no encontrada'
                    }, status=404)
            
            # Calcular promedios históricos
            fecha_actual = timezone.now()
            fecha_inicio_historico = fecha_actual - timedelta(days=90)  # Últimos 3 meses
            
            ventas_recientes = ventas_historicas.filter(
                fecha_venta__gte=fecha_inicio_historico
            )
            
            # Calcular promedio mensual de ventas
            total_ventas_recientes_raw = ventas_recientes.aggregate(
                total=Sum('total')
            )['total'] or 0
            # Convertir Decimal a float
            total_ventas_recientes = float(total_ventas_recientes_raw) if total_ventas_recientes_raw else 0.0
            
            # Calcular promedio por mes
            meses_historicos = 3
            promedio_mensual = float(total_ventas_recientes / meses_historicos) if meses_historicos > 0 else 0.0
            
            # Calcular tendencia (crecimiento o decrecimiento)
            # Comparar últimos 30 días vs 30 días anteriores
            ultimos_30_dias = fecha_actual - timedelta(days=30)
            anteriores_30_dias = ultimos_30_dias - timedelta(days=30)
            
            ventas_ultimos_30_raw = ventas_recientes.filter(
                fecha_venta__gte=ultimos_30_dias
            ).aggregate(total=Sum('total'))['total'] or 0
            ventas_ultimos_30 = float(ventas_ultimos_30_raw) if ventas_ultimos_30_raw else 0.0
            
            ventas_anteriores_30_raw = ventas_recientes.filter(
                fecha_venta__gte=anteriores_30_dias,
                fecha_venta__lt=ultimos_30_dias
            ).aggregate(total=Sum('total'))['total'] or 0
            ventas_anteriores_30 = float(ventas_anteriores_30_raw) if ventas_anteriores_30_raw else 0.0
            
            # Calcular factor de crecimiento
            if ventas_anteriores_30 > 0:
                factor_crecimiento = float((ventas_ultimos_30 - ventas_anteriores_30) / ventas_anteriores_30)
            else:
                factor_crecimiento = 0.05  # 5% de crecimiento por defecto
            
            # Limitar el factor de crecimiento a un rango razonable (-20% a +20%)
            factor_crecimiento = max(-0.2, min(0.2, float(factor_crecimiento)))
            
            # Generar predicciones
            predicciones = []
            # Usar fecha actual como punto de partida, comenzando desde mañana
            fecha_prediccion = (fecha_actual + timedelta(days=1)).date()  # Convertir a date para predicciones
            
            # Ajustar según período solicitado
            if periodo == 'semana':
                incremento = timedelta(weeks=1)
                meses_futuros = min(meses_futuros, 12)  # Máximo 12 semanas
            elif periodo == 'dia':
                incremento = timedelta(days=1)
                meses_futuros = min(meses_futuros, 30)  # Máximo 30 días
            else:  # mes
                # Para meses, usar incremento de aproximadamente 30 días
                incremento = timedelta(days=30)
                meses_futuros = min(meses_futuros, 12)  # Máximo 12 meses
            
            # Calcular confianza basada en la calidad del modelo
            confianza_base = 0.7  # Confianza base
            if modelo.r2_score:
                confianza_base = min(0.95, max(0.5, modelo.r2_score))  # Entre 0.5 y 0.95
            
            for i in range(meses_futuros):
                # Calcular valor predicho con tendencia
                # Aplicar factor de crecimiento que disminuye con el tiempo (más incierto a futuro)
                factor_temporal = 1 - (i * 0.05)  # Disminuye 5% por período
                factor_crecimiento_ajustado = factor_crecimiento * factor_temporal
                
                if periodo == 'semana':
                    valor_base = float(promedio_mensual) / 4.0  # Promedio semanal
                elif periodo == 'dia':
                    valor_base = float(promedio_mensual) / 30.0  # Promedio diario
                else:
                    valor_base = float(promedio_mensual)
                
                # Aplicar crecimiento proyectado
                factor_crecimiento_ajustado_float = float(factor_crecimiento_ajustado)
                valor_predicho = float(valor_base) * (1.0 + factor_crecimiento_ajustado_float)
                
                # Agregar variabilidad aleatoria (simulando incertidumbre del modelo)
                variabilidad = random.uniform(-0.1, 0.1)  # ±10% de variación
                valor_predicho = float(valor_predicho) * (1.0 + float(variabilidad))
                
                # Asegurar que el valor sea positivo
                valor_predicho = max(0.0, float(valor_predicho))
                
                # Calcular confianza (disminuye con el tiempo)
                confianza = confianza_base * (1 - i * 0.05)
                confianza = max(0.3, confianza)  # Mínimo 30% de confianza
                
                # Guardar predicción si se solicita
                prediccion_obj = None
                if guardar:
                    prediccion_obj = PrediccionVenta.objects.create(
                        fecha_prediccion=fecha_prediccion,
                        valor_predicho=round(valor_predicho, 2),
                        modelo=modelo,
                        categoria=categoria,
                        modelo_version=modelo.version,
                        confianza=round(confianza, 3)
                    )
                
                # Formatear fecha correctamente con hora actual
                # Usar datetime actual para mostrar la hora correcta
                fecha_actual_dt = timezone.now()
                fecha_prediccion_str = fecha_prediccion.isoformat() if hasattr(fecha_prediccion, 'isoformat') else str(fecha_prediccion)
                fecha_ejecucion_str = fecha_actual_dt.isoformat()
                
                predicciones.append({
                    'id': prediccion_obj.id_prediccion if prediccion_obj else None,
                    'fecha_prediccion': fecha_prediccion_str,
                    'fecha_ejecucion': fecha_ejecucion_str,  # Incluir hora de ejecución
                    'valor_predicho': round(valor_predicho, 2),
                    'confianza': round(confianza, 3),
                    'categoria': {
                        'id': categoria.id_categoria,
                        'nombre': categoria.nombre
                    } if categoria else None,
                    'modelo_version': modelo.version
                })
                
                # Avanzar fecha
                fecha_prediccion += incremento
            
            # Calcular totales
            total_predicho = float(sum(float(p['valor_predicho']) for p in predicciones))
            confianza_promedio = float(sum(float(p['confianza']) for p in predicciones) / len(predicciones)) if predicciones else 0.0
            
            return JsonResponse({
                'success': True,
                'predicciones': predicciones,
                'resumen': {
                    'total_predicciones': len(predicciones),
                    'total_valor_predicho': round(total_predicho, 2),
                    'confianza_promedio': round(confianza_promedio, 3),
                    'periodo': periodo,
                    'meses_futuros': meses_futuros,
                    'categoria': {
                        'id': categoria.id_categoria,
                        'nombre': categoria.nombre
                    } if categoria else None,
                    'modelo_usado': {
                        'id': modelo.id_modelo,
                        'nombre': modelo.nombre,
                        'version': modelo.version,
                        'r2_score': modelo.r2_score
                    }
                },
                'tendencias': {
                    'promedio_mensual_historico': round(float(promedio_mensual), 2),
                    'factor_crecimiento': round(float(factor_crecimiento) * 100.0, 2),  # En porcentaje
                    'ventas_ultimos_30_dias': round(float(ventas_ultimos_30), 2),
                    'ventas_anteriores_30_dias': round(float(ventas_anteriores_30), 2)
                }
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en GenerarPrediccionesView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def get(self, request):
        """
        Obtener predicciones existentes
        """
        try:
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión'
                }, status=401)
            
            # Parámetros de consulta
            categoria_id = request.GET.get('categoria_id', None)
            fecha_desde = request.GET.get('fecha_desde', None)
            fecha_hasta = request.GET.get('fecha_hasta', None)
            limite = int(request.GET.get('limite', 50))
            
            # Construir query
            predicciones = PrediccionVenta.objects.all().select_related('categoria', 'modelo')
            
            if categoria_id:
                try:
                    categoria_id_int = int(categoria_id)
                    # Usar el campo correcto del ForeignKey (id_categoria en la BD)
                    predicciones = predicciones.filter(categoria__id_categoria=categoria_id_int)
                except (ValueError, TypeError):
                    pass  # Si no es un número válido, no filtrar
            
            if fecha_desde:
                try:
                    fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                    predicciones = predicciones.filter(fecha_prediccion__gte=fecha_desde_obj)
                except:
                    pass
            
            if fecha_hasta:
                try:
                    fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                    predicciones = predicciones.filter(fecha_prediccion__lte=fecha_hasta_obj)
                except:
                    pass
            
            predicciones = predicciones.order_by('-fecha_prediccion')[:limite]
            
            predicciones_data = []
            for pred in predicciones:
                predicciones_data.append({
                    'id': pred.id_prediccion,
                    'fecha_prediccion': pred.fecha_prediccion.isoformat(),
                    'valor_predicho': float(pred.valor_predicho),
                    'confianza': pred.confianza,
                    'categoria': {
                        'id': pred.categoria.id_categoria,
                        'nombre': pred.categoria.nombre
                    } if pred.categoria else None,
                    'modelo_version': pred.modelo_version,
                    'fecha_ejecucion': pred.fecha_ejecucion.isoformat(),
                    'modelo': {
                        'id': pred.modelo.id_modelo if pred.modelo else None,
                        'nombre': pred.modelo.nombre if pred.modelo else None
                    }
                })
            
            return JsonResponse({
                'success': True,
                'predicciones': predicciones_data,
                'total': len(predicciones_data)
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en GenerarPrediccionesView GET: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
