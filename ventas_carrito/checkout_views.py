from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json

from .models import Carrito, ItemCarrito, Venta, DetalleVenta


# ==========================================================
# CASO DE USO 10: REALIZAR COMPRA (CHECKOUT)
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class CheckoutView(View):
    """
    CU10: Realizar Compra (Checkout)
    Permite a clientes autenticados realizar compras desde su carrito
    """
    
    def get(self, request):
        """Mostrar información del endpoint de checkout"""
        return JsonResponse({
            'endpoint': 'Checkout API',
            'method': 'POST',
            'description': 'Realizar compra desde el carrito',
            'required_fields': ['metodo_pago', 'direccion_entrega'],
            'optional_fields': ['notas'],
            'example': {
                'metodo_pago': 'stripe',  # ÚNICO método permitido
                'direccion_entrega': 'Calle 123, #45, Ciudad',
                'notas': 'Entregar en horario de oficina'
            },
            'note': 'Requires authenticated user with items in cart'
        })
    
    def post(self, request):
        try:
            # Verificar que el usuario esté autenticado
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'Debe iniciar sesión para realizar compras'
                }, status=401)
            
            # Obtener datos del request
            data = json.loads(request.body)
            # FORZAR que siempre sea Stripe - no se acepta otro método
            metodo_pago = 'stripe'  # SOLO Stripe permitido
            direccion_entrega = data.get('direccion_entrega', '')
            notas = data.get('notas', '')
            
            # Validaciones básicas
            if not direccion_entrega.strip():
                return JsonResponse({
                    'success': False,
                    'message': 'La dirección de entrega es obligatoria'
                }, status=400)
            
            # Obtener cliente autenticado
            user_id = request.session.get('user_id')
            try:
                from autenticacion_usuarios.models import Usuario, Cliente
                usuario = Usuario.objects.get(id=user_id)
                cliente = Cliente.objects.get(id=usuario)
            except (Usuario.DoesNotExist, Cliente.DoesNotExist):
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            # Obtener carrito del cliente
            try:
                carrito = Carrito.objects.get(cliente=cliente, activo=True)
            except Carrito.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'No hay productos en el carrito'
                }, status=400)
            
            # Verificar que el carrito tenga items
            items_carrito = ItemCarrito.objects.filter(carrito=carrito)
            if not items_carrito.exists():
                return JsonResponse({
                    'success': False,
                    'message': 'El carrito está vacío'
                }, status=400)
            
            # Calcular total
            total = sum(item.get_subtotal() for item in items_carrito)
            
            # Crear venta
            venta = Venta.objects.create(
                cliente=cliente,
                total=total,
                estado='pendiente',
                metodo_pago=metodo_pago,
                direccion_entrega=direccion_entrega,
                notas=notas
            )
            
            # Notificar a administradores sobre nueva venta
            try:
                from autenticacion_usuarios.notificaciones_views import notificar_nueva_venta
                notificar_nueva_venta(venta)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error notificando nueva venta: {str(e)}")
            
            # Crear detalles de venta y actualizar stock
            from productos.models import Stock
            import logging
            logger = logging.getLogger(__name__)
            
            detalles_creados = []
            productos_sin_stock = []
            
            # Primero verificar todo el stock disponible
            for item in items_carrito.select_related('producto'):
                stock_obj = Stock.objects.filter(producto=item.producto).first()
                stock_disponible = stock_obj.cantidad if stock_obj else 0
                
                if stock_disponible < item.cantidad:
                    productos_sin_stock.append({
                        'producto': item.producto.nombre,
                        'solicitado': item.cantidad,
                        'disponible': stock_disponible
                    })
            
            # Si hay productos sin stock, cancelar la venta
            if productos_sin_stock:
                venta.delete()
                mensaje = 'Stock insuficiente para los siguientes productos: '
                mensaje += ', '.join([f"{p['producto']} (solicitado: {p['solicitado']}, disponible: {p['disponible']})" 
                                    for p in productos_sin_stock])
                return JsonResponse({
                    'success': False,
                    'message': mensaje
                }, status=400)
            
            # Si todo está bien, crear detalles y actualizar stock
            for item in items_carrito.select_related('producto'):
                # Crear detalle de venta
                detalle = DetalleVenta.objects.create(
                    venta=venta,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario
                )
                detalles_creados.append(detalle)
                
                # Actualizar stock del producto
                stock_obj = Stock.objects.filter(producto=item.producto).first()
                if stock_obj:
                    stock_obj.cantidad -= item.cantidad
                    if stock_obj.cantidad < 0:
                        stock_obj.cantidad = 0
                    stock_obj.save()
                else:
                    logger.warning(f"Producto {item.producto.id} no tiene registro de stock")
            
            # Marcar venta como completada
            venta.estado = 'completada'
            venta.save()
            
            # CU12: Generar comprobante automáticamente
            comprobante_data = None
            try:
                from .comprobantes_views import ComprobanteView
                comprobante_view = ComprobanteView()
                comprobante = comprobante_view._generar_comprobante(venta, 'factura')
                comprobante_data = {
                    'id': comprobante.id_comprobante,
                    'numero': comprobante.nro,
                    'pdf_url': f'/api/ventas/comprobantes/{venta.id_venta}/pdf/'
                }
            except Exception as e:
                logger.warning(f"Error al generar comprobante automático: {str(e)}")
                # No fallar la venta si el comprobante falla
            
            # Limpiar carrito
            items_carrito.delete()
            carrito.delete()
            
            # Registrar en bitácora
            from autenticacion_usuarios.models import Bitacora
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='COMPRA_REALIZADA',
                modulo='VENTAS',
                descripcion=f'Cliente {usuario.nombre} realizó compra por ${total}',
                ip=self.get_client_ip(request)
            )
            
            # Respuesta exitosa
            response_data = {
                'success': True,
                'message': 'Compra realizada exitosamente',
                'venta': {
                    'id': venta.id_venta,
                    'total': float(venta.total),
                    'fecha': venta.fecha_venta.isoformat(),
                    'estado': venta.estado,
                    'metodo_pago': venta.metodo_pago,
                    'direccion_entrega': venta.direccion_entrega,
                    'productos': len(detalles_creados)
                }
            }
            
            if comprobante_data:
                response_data['comprobante'] = comprobante_data
            
            return JsonResponse(response_data, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en CheckoutView.post: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
