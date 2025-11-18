from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Sum, Count, Avg, Max, Q
from django.utils import timezone
from datetime import timedelta
import json
import logging

from .models import Usuario, Rol, Bitacora, Cliente

# Importar modelos de ventas si existen
try:
    from ventas_carrito.models import Venta, DetalleVenta
except ImportError:
    Venta = None
    DetalleVenta = None

logger = logging.getLogger(__name__)

# ==========================================================
# CASO DE USO 1: INICIAR SESIÓN
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    """
    CU1: Iniciar Sesión
    Permite a usuarios (clientes y administradores) autenticarse en el sistema
    """
    
    def get(self, request):
        """Mostrar información del endpoint de login"""
        return JsonResponse({
            'endpoint': 'Login API',
            'method': 'POST',
            'description': 'Iniciar sesión en el sistema',
            'required_fields': ['email', 'contrasena'],
            'example': {
                'email': 'admin@tienda.com',
                'contrasena': 'admin123'
            },
            'note': 'Use POST method to login'
        })
    
    def post(self, request):
        try:
            # Obtener datos del request
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            contrasena = data.get('contrasena', '')
            
            # Validaciones básicas
            if not email or not contrasena:
                return JsonResponse({
                    'success': False,
                    'message': 'Email y contraseña son requeridos'
                }, status=400)
            
            # Buscar usuario por email
            try:
                usuario = Usuario.objects.get(email=email)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }, status=401)
            
            # Verificar si el usuario está activo
            if not usuario.is_active():
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario inactivo. Contacte al administrador.'
                }, status=401)
            
            # Verificar contraseña (hash o texto plano para entorno académico)
            if not (usuario.check_password(contrasena) or usuario.contrasena == contrasena):
                return JsonResponse({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }, status=401)
            
            # Obtener IP del cliente
            ip_address = self.get_client_ip(request)
            
            # Registrar en bitácora
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='INICIO_SESION',
                modulo='AUTENTICACION',
                descripcion=f'Usuario {usuario.nombre} inició sesión',
                ip=ip_address
            )
            
            # Crear sesión
            request.session['user_id'] = usuario.id
            request.session['user_email'] = usuario.email
            request.session['user_nombre'] = usuario.nombre
            request.session['user_rol'] = usuario.id_rol.nombre
            request.session['is_authenticated'] = True
            
            # Respuesta exitosa
            response_data = {
                'success': True,
                'message': 'Sesión iniciada correctamente',
                'user': {
                    'id': usuario.id,
                    'nombre': usuario.nombre,
                    'apellido': usuario.apellido,
                    'email': usuario.email,
                    'rol': usuario.id_rol.nombre,
                    'telefono': usuario.telefono
                }
            }
            
            # Si es cliente, agregar información adicional
            if usuario.id_rol.nombre.lower() == 'cliente':
                try:
                    cliente = usuario.cliente
                    response_data['user']['direccion'] = cliente.direccion
                    response_data['user']['ciudad'] = cliente.ciudad
                except:
                    pass  # Si no tiene registro de cliente, no pasa nada
            
            return JsonResponse(response_data, status=200)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Error interno del servidor'
            }, status=500)
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

# ==========================================================
# CASO DE USO 2: CERRAR SESIÓN
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(View):
    """
    CU2: Cerrar Sesión
    Permite a usuarios autenticados cerrar su sesión en el sistema
    """
    
    def get(self, request):
        """Mostrar información del endpoint de logout"""
        return JsonResponse({
            'endpoint': 'Logout API',
            'method': 'POST',
            'description': 'Cerrar sesión en el sistema',
            'required_fields': [],
            'note': 'Use POST method to logout. Requires active session.'
        })
    
    def post(self, request):
        try:
            # Verificar si hay sesión activa
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No hay sesión activa'
                }, status=400)
            
            # Obtener información del usuario
            user_id = request.session.get('user_id')
            user_nombre = request.session.get('user_nombre', 'Usuario')
            
            # Obtener IP del cliente
            ip_address = self.get_client_ip(request)
            
            # Registrar en bitácora
            if user_id:
                try:
                    usuario = Usuario.objects.get(id=user_id)
                    Bitacora.objects.create(
                        id_usuario=usuario,
                        accion='CIERRE_SESION',
                        modulo='AUTENTICACION',
                        descripcion=f'Usuario {usuario.nombre} cerró sesión',
                        ip=ip_address
                    )
                except Usuario.DoesNotExist:
                    pass  # Si no existe el usuario, continuar con el logout
            
            # Limpiar sesión
            request.session.flush()
            
            return JsonResponse({
                'success': True,
                'message': 'Sesión cerrada correctamente'
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en logout: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Error interno del servidor'
            }, status=500)
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

# ==========================================================
# VISTA AUXILIAR: VERIFICAR SESIÓN
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class CheckSessionView(View):
    """
    Vista auxiliar para verificar si hay una sesión activa
    """
    
    def get(self, request):
        try:
            if request.session.get('is_authenticated'):
                user_id = request.session.get('user_id')
                try:
                    usuario = Usuario.objects.get(id=user_id)
                    return JsonResponse({
                        'success': True,
                        'authenticated': True,
                        'user': {
                            'id': usuario.id,
                            'nombre': usuario.nombre,
                            'apellido': usuario.apellido,
                            'email': usuario.email,
                            'rol': usuario.id_rol.nombre,
                            'telefono': usuario.telefono
                        }
                    })
                except Usuario.DoesNotExist:
                    request.session.flush()
                    return JsonResponse({
                        'success': True,
                        'authenticated': False
                    })
            else:
                return JsonResponse({
                    'success': True,
                    'authenticated': False
                })
        except Exception as e:
            logger.error(f"Error verificando sesión: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Error interno del servidor'
            }, status=500)


# ==========================================================
# CASO DE USO 3: REGISTRAR CUENTA DEL CLIENTE
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(View):
    """
    CU3: Registrar Cuenta del Cliente
    Permite a nuevos usuarios registrarse como clientes en el sistema
    """
    
    def get(self, request):
        """Mostrar información del endpoint de registro"""
        return JsonResponse({
            'endpoint': 'Register API',
            'method': 'POST',
            'description': 'Registrar nueva cuenta de cliente',
            'required_fields': ['nombre', 'apellido', 'email', 'contrasena', 'telefono'],
            'optional_fields': ['direccion', 'ciudad'],
            'example': {
                'nombre': 'Juan',
                'apellido': 'Pérez',
                'email': 'juan@email.com',
                'contrasena': 'miPassword123',
                'telefono': '+1234567890',
                'direccion': 'Calle 123, #45',
                'ciudad': 'Ciudad'
            },
            'note': 'Use POST method to register. Email must be unique.'
        })
    
    def post(self, request):
        try:
            # Obtener datos del request
            data = json.loads(request.body)
            
            # Campos obligatorios
            nombre = data.get('nombre', '').strip()
            apellido = data.get('apellido', '').strip()
            email = data.get('email', '').strip().lower()
            contrasena = data.get('contrasena', '')
            telefono = data.get('telefono', '').strip()
            
            # Campos opcionales
            direccion = data.get('direccion', '').strip()
            ciudad = data.get('ciudad', '').strip()
            tipo_cuenta = data.get('tipoCuenta', 'Cliente').strip()
            
            # Validaciones básicas
            if not nombre:
                return JsonResponse({
                    'success': False,
                    'message': 'El nombre es obligatorio'
                }, status=400)
            
            if not email:
                return JsonResponse({
                    'success': False,
                    'message': 'El email es obligatorio'
                }, status=400)
            
            if not contrasena:
                return JsonResponse({
                    'success': False,
                    'message': 'La contraseña es obligatoria'
                }, status=400)
            
            if len(contrasena) < 6:
                return JsonResponse({
                    'success': False,
                    'message': 'La contraseña debe tener al menos 6 caracteres'
                }, status=400)
            
            # Validar formato de email básico
            if '@' not in email or '.' not in email:
                return JsonResponse({
                    'success': False,
                    'message': 'Formato de email inválido'
                }, status=400)
            
            # Verificar si el email ya existe
            if Usuario.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Este email ya está registrado'
                }, status=400)
            
            # Validar y obtener rol
            tipo_cuenta_normalizado = tipo_cuenta.capitalize()
            if tipo_cuenta_normalizado not in ['Cliente', 'Administrador']:
                return JsonResponse({
                    'success': False,
                    'message': 'Tipo de cuenta inválido. Debe ser Cliente o Administrador'
                }, status=400)
            
            # Obtener o crear rol
            try:
                rol = Rol.objects.get(nombre=tipo_cuenta_normalizado)
            except Rol.DoesNotExist:
                rol = Rol.objects.create(nombre=tipo_cuenta_normalizado)
            
            # Crear usuario
            usuario = Usuario.objects.create(
                nombre=nombre,
                apellido=apellido,
                email=email,
                telefono=telefono,
                id_rol=rol,
                estado=True
            )
            
            # Encriptar contraseña
            usuario.set_password(contrasena)
            usuario.save()
            
            # Solo crear registro de cliente si el rol es Cliente
            if tipo_cuenta_normalizado == 'Cliente':
                cliente, created = Cliente.objects.get_or_create(
                    id=usuario,
                    defaults={
                        'direccion': direccion,
                        'ciudad': ciudad
                    }
                )
                
                # Si ya existía, actualizar datos
                if not created:
                    cliente.direccion = direccion
                    cliente.ciudad = ciudad
                    cliente.save()
            
            # Obtener IP del cliente
            ip_address = self.get_client_ip(request)
            
            # Registrar en bitácora
            accion_bitacora = 'REGISTRO_CLIENTE' if tipo_cuenta_normalizado == 'Cliente' else 'REGISTRO_ADMINISTRADOR'
            descripcion_bitacora = f'Nuevo {tipo_cuenta_normalizado.lower()} registrado: {usuario.nombre} {usuario.apellido}'
            
            Bitacora.objects.create(
                id_usuario=usuario,
                accion=accion_bitacora,
                modulo='AUTENTICACION',
                descripcion=descripcion_bitacora,
                ip=ip_address
            )
            
            # Auto login: crear sesión para el nuevo usuario
            request.session['user_id'] = usuario.id
            request.session['user_email'] = usuario.email
            request.session['user_nombre'] = usuario.nombre
            request.session['user_rol'] = tipo_cuenta_normalizado
            request.session['is_authenticated'] = True

            # Preparar respuesta
            user_response = {
                'id': usuario.id,
                'nombre': usuario.nombre,
                'apellido': usuario.apellido,
                'email': usuario.email,
                'telefono': usuario.telefono,
                'rol': tipo_cuenta_normalizado
            }
            
            # Agregar datos de cliente solo si es cliente
            if tipo_cuenta_normalizado == 'Cliente':
                cliente = Cliente.objects.get(id=usuario)
                user_response['direccion'] = cliente.direccion
                user_response['ciudad'] = cliente.ciudad
            
            mensaje_exito = f'Cuenta de {tipo_cuenta_normalizado.lower()} creada exitosamente'
            
            # Respuesta exitosa
            return JsonResponse({
                'success': True,
                'message': mensaje_exito,
                'user': user_response
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en registro: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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


# ==========================================================
# CASO DE USO: GESTIÓN DE CLIENTES (CRUD)
# ==========================================================

@method_decorator(csrf_exempt, name='dispatch')
class ClientesListView(View):
    """
    Listar todos los clientes
    GET: Obtener lista de clientes
    """
    
    def get(self, request):
        try:
            # Verificar que el usuario sea administrador
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No autenticado'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                if usuario.id_rol.nombre.lower() != 'administrador':
                    return JsonResponse({
                        'success': False,
                        'message': 'No autorizado. Solo administradores pueden ver clientes.'
                    }, status=403)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=401)
            
            # Obtener parámetros de búsqueda y filtro
            search = request.GET.get('search', '').strip()
            estado_filter = request.GET.get('estado', '').strip()
            ciudad_filter = request.GET.get('ciudad', '').strip()
            
            # Obtener todos los clientes con información del usuario
            clientes = Cliente.objects.select_related('id').all()
            
            # Aplicar filtros de búsqueda
            if search:
                clientes = clientes.filter(
                    Q(id__nombre__icontains=search) |
                    Q(id__apellido__icontains=search) |
                    Q(id__email__icontains=search) |
                    Q(id__telefono__icontains=search)
                )
            
            if estado_filter:
                estado_bool = estado_filter.lower() in ['activo', 'true', '1']
                clientes = clientes.filter(id__estado=estado_bool)
            
            if ciudad_filter:
                clientes = clientes.filter(ciudad__icontains=ciudad_filter)
            
            # Obtener estadísticas básicas de ventas para cada cliente
            clientes_data = []
            for cliente in clientes:
                usuario_cliente = cliente.id
                
                # Calcular estadísticas básicas de ventas
                stats = self._get_cliente_stats_basic(cliente)
                
                clientes_data.append({
                    'id': usuario_cliente.id,
                    'nombre': f"{usuario_cliente.nombre} {usuario_cliente.apellido or ''}".strip(),
                    'apellido': usuario_cliente.apellido or '',
                    'email': usuario_cliente.email,
                    'telefono': usuario_cliente.telefono or '',
                    'direccion': cliente.direccion or '',
                    'ciudad': cliente.ciudad or '',
                    'estado': 'Activo' if usuario_cliente.estado else 'Inactivo',
                    'total_compras': stats['total_compras'],
                    'monto_total': float(stats['monto_total']),
                    'ultima_compra': stats['ultima_compra']
                })
            
            # Ordenamiento
            sort_by = request.GET.get('sort_by', 'id')
            sort_order = request.GET.get('sort_order', 'asc')
            
            if sort_by == 'nombre':
                clientes_data.sort(key=lambda x: x['nombre'].lower(), reverse=(sort_order == 'desc'))
            elif sort_by == 'monto_total':
                clientes_data.sort(key=lambda x: x['monto_total'], reverse=(sort_order == 'desc'))
            elif sort_by == 'total_compras':
                clientes_data.sort(key=lambda x: x['total_compras'], reverse=(sort_order == 'desc'))
            
            return JsonResponse({
                'success': True,
                'clientes': clientes_data,
                'total': len(clientes_data)
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error listando clientes: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _get_cliente_stats_basic(self, cliente):
        """Obtener estadísticas básicas de un cliente"""
        stats = {
            'total_compras': 0,
            'monto_total': 0.0,
            'ultima_compra': None
        }
        
        if Venta:
            try:
                ventas = Venta.objects.filter(cliente=cliente)
                stats['total_compras'] = ventas.count()
                
                if stats['total_compras'] > 0:
                    total = ventas.aggregate(Sum('total'))['total__sum'] or 0.0
                    stats['monto_total'] = float(total)
                    
                    ultima_venta = ventas.order_by('-fecha_venta').first()
                    if ultima_venta:
                        stats['ultima_compra'] = ultima_venta.fecha_venta.strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error obteniendo stats básicas: {str(e)}")
        
        return stats


@method_decorator(csrf_exempt, name='dispatch')
class ClienteDetailView(View):
    """
    Ver, actualizar o eliminar un cliente específico
    GET: Obtener detalles del cliente
    PUT: Actualizar cliente
    DELETE: Desactivar cliente
    """
    
    def get(self, request, cliente_id):
        try:
            # Verificar autenticación y autorización
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No autenticado'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                if usuario.id_rol.nombre.lower() != 'administrador':
                    return JsonResponse({
                        'success': False,
                        'message': 'No autorizado'
                    }, status=403)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=401)
            
            # Obtener cliente
            try:
                cliente = Cliente.objects.select_related('id').get(id=cliente_id)
            except Cliente.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            usuario_cliente = cliente.id
            
            # Obtener estadísticas detalladas
            stats = self._get_cliente_stats_detailed(cliente)
            
            cliente_data = {
                'id': usuario_cliente.id,
                'nombre': usuario_cliente.nombre,
                'apellido': usuario_cliente.apellido or '',
                'email': usuario_cliente.email,
                'telefono': usuario_cliente.telefono or '',
                'direccion': cliente.direccion or '',
                'ciudad': cliente.ciudad or '',
                'estado': 'Activo' if usuario_cliente.estado else 'Inactivo',
                'estadisticas': stats
            }
            
            return JsonResponse({
                'success': True,
                'cliente': cliente_data
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error obteniendo cliente: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _get_cliente_stats_detailed(self, cliente):
        """Obtener estadísticas detalladas de un cliente"""
        stats = {
            'total_compras': 0,
            'monto_total': 0.0,
            'promedio_compra': 0.0,
            'ultima_compra': None,
            'primera_compra': None,
            'compras_mes_actual': 0,
            'monto_mes_actual': 0.0,
            'dias_desde_ultima_compra': None,
            'antiguedad_dias': None
        }
        
        if Venta:
            try:
                ventas = Venta.objects.filter(cliente=cliente)
                total_ventas = ventas.count()
                stats['total_compras'] = total_ventas
                
                if total_ventas > 0:
                    # Monto total
                    total = ventas.aggregate(Sum('total'))['total__sum'] or 0.0
                    stats['monto_total'] = float(total)
                    
                    # Promedio
                    stats['promedio_compra'] = float(total / total_ventas)
                    
                    # Última compra
                    ultima_venta = ventas.order_by('-fecha_venta').first()
                    if ultima_venta:
                        stats['ultima_compra'] = ultima_venta.fecha_venta.strftime('%Y-%m-%d %H:%M:%S')
                        dias_desde = (timezone.now() - ultima_venta.fecha_venta).days
                        stats['dias_desde_ultima_compra'] = dias_desde
                    
                    # Primera compra
                    primera_venta = ventas.order_by('fecha_venta').first()
                    if primera_venta:
                        stats['primera_compra'] = primera_venta.fecha_venta.strftime('%Y-%m-%d')
                        antiguedad = (timezone.now() - primera_venta.fecha_venta).days
                        stats['antiguedad_dias'] = antiguedad
                    
                    # Compras del mes actual
                    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    ventas_mes = ventas.filter(fecha_venta__gte=inicio_mes)
                    stats['compras_mes_actual'] = ventas_mes.count()
                    
                    if stats['compras_mes_actual'] > 0:
                        monto_mes = ventas_mes.aggregate(Sum('total'))['total__sum'] or 0.0
                        stats['monto_mes_actual'] = float(monto_mes)
            except Exception as e:
                logger.error(f"Error obteniendo stats detalladas: {str(e)}")
        
        return stats
    
    def put(self, request, cliente_id):
        try:
            # Verificar autenticación y autorización
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No autenticado'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                if usuario.id_rol.nombre.lower() != 'administrador':
                    return JsonResponse({
                        'success': False,
                        'message': 'No autorizado'
                    }, status=403)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=401)
            
            # Obtener datos del request
            data = json.loads(request.body)
            
            # Obtener cliente
            try:
                cliente = Cliente.objects.select_related('id').get(id=cliente_id)
            except Cliente.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            usuario_cliente = cliente.id
            
            # Actualizar campos del usuario
            if 'nombre' in data:
                usuario_cliente.nombre = data['nombre'].strip()
            if 'apellido' in data:
                usuario_cliente.apellido = data.get('apellido', '').strip()
            if 'email' in data:
                nuevo_email = data['email'].strip().lower()
                # Verificar que el email no esté en uso por otro usuario
                if nuevo_email != usuario_cliente.email:
                    if Usuario.objects.filter(email=nuevo_email).exclude(id=usuario_cliente.id).exists():
                        return JsonResponse({
                            'success': False,
                            'message': 'Este email ya está en uso por otro usuario'
                        }, status=400)
                usuario_cliente.email = nuevo_email
            if 'telefono' in data:
                usuario_cliente.telefono = data.get('telefono', '').strip()
            if 'estado' in data:
                estado_str = str(data['estado']).lower()
                usuario_cliente.estado = estado_str in ['activo', 'true', '1', 'yes']
            
            usuario_cliente.save()
            
            # Actualizar campos del cliente
            if 'direccion' in data:
                cliente.direccion = data.get('direccion', '').strip()
            if 'ciudad' in data:
                cliente.ciudad = data.get('ciudad', '').strip()
            
            cliente.save()
            
            # Registrar en bitácora
            ip_address = self.get_client_ip(request)
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='ACTUALIZAR_CLIENTE',
                modulo='GESTION_CLIENTES',
                descripcion=f'Cliente {usuario_cliente.nombre} actualizado',
                ip=ip_address
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Cliente actualizado correctamente',
                'cliente': {
                    'id': usuario_cliente.id,
                    'nombre': usuario_cliente.nombre,
                    'apellido': usuario_cliente.apellido or '',
                    'email': usuario_cliente.email,
                    'telefono': usuario_cliente.telefono or '',
                    'direccion': cliente.direccion or '',
                    'ciudad': cliente.ciudad or '',
                    'estado': 'Activo' if usuario_cliente.estado else 'Inactivo'
                }
            }, status=200)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error actualizando cliente: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def delete(self, request, cliente_id):
        try:
            # Verificar autenticación y autorización
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No autenticado'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                if usuario.id_rol.nombre.lower() != 'administrador':
                    return JsonResponse({
                        'success': False,
                        'message': 'No autorizado'
                    }, status=403)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=401)
            
            # Obtener cliente
            try:
                cliente = Cliente.objects.select_related('id').get(id=cliente_id)
            except Cliente.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            usuario_cliente = cliente.id
            
            # Desactivar cliente (no eliminar físicamente)
            usuario_cliente.estado = False
            usuario_cliente.save()
            
            # Registrar en bitácora
            ip_address = self.get_client_ip(request)
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='DESACTIVAR_CLIENTE',
                modulo='GESTION_CLIENTES',
                descripcion=f'Cliente {usuario_cliente.nombre} desactivado',
                ip=ip_address
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Cliente desactivado correctamente'
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error desactivando cliente: {str(e)}")
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


@method_decorator(csrf_exempt, name='dispatch')
class ClienteVentasView(View):
    """
    Obtener historial de compras de un cliente
    GET: Listar todas las ventas del cliente
    """
    
    def get(self, request, cliente_id):
        try:
            # Verificar autenticación y autorización
            if not request.session.get('is_authenticated'):
                return JsonResponse({
                    'success': False,
                    'message': 'No autenticado'
                }, status=401)
            
            user_id = request.session.get('user_id')
            try:
                usuario = Usuario.objects.get(id=user_id)
                if usuario.id_rol.nombre.lower() != 'administrador':
                    return JsonResponse({
                        'success': False,
                        'message': 'No autorizado'
                    }, status=403)
            except Usuario.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }, status=401)
            
            # Obtener cliente
            try:
                cliente = Cliente.objects.get(id=cliente_id)
            except Cliente.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Cliente no encontrado'
                }, status=404)
            
            # Obtener parámetros de filtro
            fecha_desde = request.GET.get('fecha_desde', '').strip()
            fecha_hasta = request.GET.get('fecha_hasta', '').strip()
            estado = request.GET.get('estado', '').strip()
            limit = request.GET.get('limit', '').strip()
            
            # Obtener ventas del cliente
            ventas_list = []
            
            if Venta:
                try:
                    ventas = Venta.objects.filter(cliente=cliente).select_related('cliente').prefetch_related('detalles', 'detalles__producto')
                    
                    # Aplicar filtros
                    if fecha_desde:
                        ventas = ventas.filter(fecha_venta__gte=fecha_desde)
                    if fecha_hasta:
                        ventas = ventas.filter(fecha_venta__lte=fecha_hasta)
                    if estado:
                        ventas = ventas.filter(estado=estado)
                    
                    # Ordenar por fecha más reciente primero
                    ventas = ventas.order_by('-fecha_venta')
                    
                    # Limitar resultados si se solicita
                    if limit:
                        try:
                            limit_int = int(limit)
                            ventas = ventas[:limit_int]
                        except ValueError:
                            pass
                    
                    # Serializar ventas con detalles
                    for venta in ventas:
                        detalles_data = []
                        if DetalleVenta:
                            detalles = venta.detalles.all()
                            for detalle in detalles:
                                detalles_data.append({
                                    'id': detalle.id_detalle,
                                    'producto_id': detalle.producto.id if detalle.producto else None,
                                    'producto_nombre': detalle.producto.nombre if detalle.producto else 'Producto eliminado',
                                    'cantidad': detalle.cantidad,
                                    'precio_unitario': float(detalle.precio_unitario),
                                    'subtotal': float(detalle.subtotal)
                                })
                        
                        ventas_list.append({
                            'id_venta': venta.id_venta,
                            'fecha_venta': venta.fecha_venta.strftime('%Y-%m-%d %H:%M:%S'),
                            'total': float(venta.total),
                            'estado': venta.estado,
                            'metodo_pago': venta.metodo_pago,
                            'direccion_entrega': venta.direccion_entrega or '',
                            'notas': venta.notas or '',
                            'detalles': detalles_data,
                            'total_productos': len(detalles_data)
                        })
                except Exception as e:
                    logger.error(f"Error obteniendo ventas: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'message': f'Error obteniendo ventas: {str(e)}'
                    }, status=500)
            
            return JsonResponse({
                'success': True,
                'ventas': ventas_list,
                'total': len(ventas_list)
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error en historial de ventas: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)

