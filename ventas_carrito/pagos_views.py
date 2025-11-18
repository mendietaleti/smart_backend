"""
CU11: Procesar Pagos en Línea
"""
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
import json
import hashlib
import secrets
import logging
from datetime import datetime

from .models import Venta, PagoOnline, MetodoPago
from autenticacion_usuarios.models import Usuario, Cliente, Bitacora

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PagoOnlineView(View):
    """
    CU11: Procesar Pagos en Línea
    Permite procesar pagos en línea para ventas
    """
    
    def get(self, request):
        """Obtener información del endpoint"""
        return JsonResponse({
            'endpoint': 'Pago Online API',
            'method': 'POST',
            'description': 'Procesar pago en línea para una venta',
            'required_fields': ['venta_id', 'numero_tarjeta', 'fecha_vencimiento', 'cvv', 'nombre_titular'],
            'example': {
                'venta_id': 1,
                'numero_tarjeta': '4111111111111111',
                'fecha_vencimiento': '12/25',
                'cvv': '123',
                'nombre_titular': 'Juan Pérez'
            }
        })
    
    def post(self, request):
        """Procesar pago en línea"""
        try:
            # Verificar autenticación
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión para procesar pagos'
                }, status=401)
            
            # Obtener datos del request
            data = json.loads(request.body)
            venta_id = data.get('venta_id')
            numero_tarjeta = data.get('numero_tarjeta', '').replace(' ', '').replace('-', '')
            fecha_vencimiento = data.get('fecha_vencimiento', '')
            cvv = data.get('cvv', '')
            nombre_titular = data.get('nombre_titular', '')
            
            # Validaciones básicas
            if not venta_id:
                return JsonResponse({
                    'success': False,
                    'message': 'ID de venta requerido'
                }, status=400)
            
            if not numero_tarjeta or len(numero_tarjeta) < 13:
                return JsonResponse({
                    'success': False,
                    'message': 'Número de tarjeta inválido'
                }, status=400)
            
            if not fecha_vencimiento:
                return JsonResponse({
                    'success': False,
                    'message': 'Fecha de vencimiento requerida'
                }, status=400)
            
            if not cvv or len(cvv) < 3:
                return JsonResponse({
                    'success': False,
                    'message': 'CVV inválido'
                }, status=400)
            
            # Obtener venta
            try:
                venta = Venta.objects.get(id_venta=venta_id)
            except Venta.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Venta no encontrada'
                }, status=404)
            
            # Verificar que la venta pertenezca al cliente autenticado
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                cliente = Cliente.objects.get(id=usuario)
                
                if venta.cliente != cliente:
                    return JsonResponse({
                        'success': False,
                        'message': 'No tiene permiso para pagar esta venta'
                    }, status=403)
            except (Usuario.DoesNotExist, Cliente.DoesNotExist):
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            # Verificar que la venta esté pendiente
            if venta.estado != 'pendiente':
                return JsonResponse({
                    'success': False,
                    'message': f'La venta ya está {venta.estado}'
                }, status=400)
            
            # Verificar que no exista ya un pago para esta venta
            if hasattr(venta, 'pago_online'):
                return JsonResponse({
                    'success': False,
                    'message': 'Ya existe un pago para esta venta'
                }, status=400)
            
            # Validar tarjeta usando algoritmo de Luhn (simplificado)
            if not self._validar_tarjeta(numero_tarjeta):
                return JsonResponse({
                    'success': False,
                    'message': 'Número de tarjeta inválido (algoritmo de Luhn)'
                }, status=400)
            
            # Simular procesamiento de pago (en producción sería con pasarela real)
            resultado_pago = self._procesar_pago_simulado(numero_tarjeta, fecha_vencimiento, cvv, venta.total)
            
            # Obtener o crear método de pago - SOLO Stripe
            metodo_pago, _ = MetodoPago.objects.get_or_create(nombre='Stripe')
            
            # Crear registro de pago
            referencia = self._generar_referencia()
            ultimos_4 = numero_tarjeta[-4:]
            hash_tarjeta = hashlib.sha256(f"{numero_tarjeta}{secrets.token_hex(8)}".encode()).hexdigest()
            
            pago_online = PagoOnline.objects.create(
                venta=venta,
                monto=venta.total,
                estado=resultado_pago['estado'],
                referencia=referencia,
                metodo_pago=metodo_pago,
                datos_tarjeta_hash=hash_tarjeta
            )
            
            # Si el pago fue exitoso, actualizar estado de la venta
            if resultado_pago['estado'] == 'exitoso':
                venta.estado = 'completada'
                venta.metodo_pago = 'stripe'  # SOLO Stripe permitido
                venta.save()
            
            # Registrar en bitácora
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='PAGO_ONLINE',
                modulo='VENTAS',
                descripcion=f'Pago en línea procesado para venta #{venta_id}. Estado: {resultado_pago["estado"]}',
                ip=self._get_client_ip(request)
            )
            
            # Respuesta
            return JsonResponse({
                'success': resultado_pago['estado'] == 'exitoso',
                'message': resultado_pago['mensaje'],
                'pago': {
                    'id': pago_online.id_pago,
                    'referencia': pago_online.referencia,
                    'monto': float(pago_online.monto),
                    'estado': pago_online.estado,
                    'fecha': pago_online.fecha.isoformat(),
                    'ultimos_4_digitos': ultimos_4
                },
                'venta': {
                    'id': venta.id_venta,
                    'estado': venta.estado,
                    'total': float(venta.total)
                }
            }, status=200 if resultado_pago['estado'] == 'exitoso' else 400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en PagoOnlineView.post: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _validar_tarjeta(self, numero):
        """Validar número de tarjeta usando algoritmo de Luhn"""
        try:
            # Eliminar espacios y guiones
            numero = numero.replace(' ', '').replace('-', '')
            
            # Verificar que sean solo dígitos
            if not numero.isdigit():
                return False
            
            # Algoritmo de Luhn
            suma = 0
            alternar = False
            
            # Recorrer de derecha a izquierda
            for digito in reversed(numero):
                n = int(digito)
                if alternar:
                    n *= 2
                    if n > 9:
                        n = (n % 10) + 1
                suma += n
                alternar = not alternar
            
            return suma % 10 == 0
        except:
            return False
    
    def _procesar_pago_simulado(self, numero_tarjeta, fecha_vencimiento, cvv, monto):
        """
        Simular procesamiento de pago
        En producción, esto se conectaría con una pasarela real (Stripe, PayPal, etc.)
        """
        # Simular validaciones
        # Tarjetas que fallan (simulación)
        tarjetas_fallidas = ['4000000000000002', '4000000000009995']
        
        if numero_tarjeta in tarjetas_fallidas:
            return {
                'estado': 'fallido',
                'mensaje': 'Pago rechazado por el banco. Verifique los datos de su tarjeta.'
            }
        
        # Tarjetas que requieren autenticación (simulación)
        tarjetas_autenticacion = ['4000000000003220']
        
        if numero_tarjeta in tarjetas_autenticacion:
            return {
                'estado': 'pendiente',
                'mensaje': 'Pago requiere autenticación adicional.'
            }
        
        # Validar fecha de vencimiento
        try:
            mes, anio = fecha_vencimiento.split('/')
            mes = int(mes)
            anio = int(anio) + 2000  # Asumir años 20XX
            
            fecha_actual = datetime.now()
            if anio < fecha_actual.year or (anio == fecha_actual.year and mes < fecha_actual.month):
                return {
                    'estado': 'fallido',
                    'mensaje': 'Tarjeta vencida'
                }
        except:
            return {
                'estado': 'fallido',
                'mensaje': 'Fecha de vencimiento inválida'
            }
        
        # Simular tiempo de procesamiento (en producción sería asíncrono)
        import time
        time.sleep(0.5)  # Simular latencia de red
        
        # Pago exitoso (simulación)
        return {
            'estado': 'exitoso',
            'mensaje': 'Pago procesado exitosamente'
        }
    
    def _generar_referencia(self):
        """Generar número de referencia único para el pago"""
        return f"PAY-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    
    def _get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@method_decorator(csrf_exempt, name='dispatch')
class EstadoPagoView(View):
    """Obtener estado de un pago"""
    
    def get(self, request, pago_id):
        try:
            pago = PagoOnline.objects.get(id_pago=pago_id)
            
            # Verificar permisos
            if request.session.get('is_authenticated'):
                user_id = request.session.get('user_id')
                try:
                    usuario = Usuario.objects.get(id=user_id)
                    cliente = Cliente.objects.get(id=usuario)
                    
                    if pago.venta.cliente != cliente:
                        return JsonResponse({
                            'success': False,
                            'message': 'No tiene permiso para ver este pago'
                        }, status=403)
                except:
                    pass
            
            return JsonResponse({
                'success': True,
                'pago': {
                    'id': pago.id_pago,
                    'referencia': pago.referencia,
                    'monto': float(pago.monto),
                    'estado': pago.estado,
                    'fecha': pago.fecha.isoformat(),
                    'venta_id': pago.venta.id_venta
                }
            }, status=200)
            
        except PagoOnline.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Pago no encontrado'
            }, status=404)
        except Exception as e:
            logger.error(f"Error en EstadoPagoView.get: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)


