"""
Vistas administrativas para gestión de datos
"""
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.management import call_command
from io import StringIO
import json
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class GenerarDatosPruebaView(View):
    """
    Endpoint para generar datos de prueba
    Solo accesible si el usuario está autenticado
    
    Nota: Los headers CORS son manejados por el middleware corsheaders
    configurado en settings.py. No es necesario agregarlos manualmente.
    """
    
    def get(self, request):
        """Método GET para verificar que el endpoint esté accesible"""
        return JsonResponse({
            'success': True,
            'message': 'Endpoint de generar datos de prueba está disponible',
            'authenticated': request.session.get('is_authenticated', False)
        })
    
    def post(self, request):
        # Verificar autenticación
        if not request.session.get('is_authenticated'):
            return JsonResponse({
                'success': False,
                'message': 'Debe iniciar sesión'
            }, status=401)
        
        try:
            # Capturar la salida del comando
            out = StringIO()
            err = StringIO()
            
            # Parámetros opcionales desde el body
            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                data = {}
            
            ventas = data.get('ventas', 120)
            productos = data.get('productos', 25)
            clientes = data.get('clientes', 12)
            limpiar = data.get('limpiar', False)
            
            # Validar parámetros
            if not isinstance(ventas, int) or ventas < 0:
                ventas = 120
            if not isinstance(productos, int) or productos < 0:
                productos = 25
            if not isinstance(clientes, int) or clientes < 0:
                clientes = 12
            if not isinstance(limpiar, bool):
                limpiar = False
            
            # Ejecutar el comando
            try:
                call_command(
                    'generar_datos_prueba',
                    ventas=ventas,
                    productos=productos,
                    clientes=clientes,
                    limpiar=limpiar,
                    stdout=out,
                    stderr=err
                )
                
                output = out.getvalue()
                errors = err.getvalue()
                
                # Extraer información útil del output
                output_lines = output.split('\n') if output else []
                summary = {}
                
                # Buscar resumen en el output
                for line in output_lines:
                    if 'Categorías:' in line:
                        summary['categorias'] = line.split(':')[-1].strip()
                    elif 'Marcas:' in line:
                        summary['marcas'] = line.split(':')[-1].strip()
                    elif 'Proveedores:' in line:
                        summary['proveedores'] = line.split(':')[-1].strip()
                    elif 'Productos:' in line:
                        summary['productos'] = line.split(':')[-1].strip()
                    elif 'Clientes:' in line:
                        summary['clientes'] = line.split(':')[-1].strip()
                    elif 'Ventas:' in line:
                        summary['ventas'] = line.split(':')[-1].strip()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Datos generados correctamente',
                    'summary': summary,
                    'output': output,
                    'errors': errors if errors else None
                })
                
            except Exception as cmd_error:
                logger.error(f"Error ejecutando comando generar_datos_prueba: {str(cmd_error)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'message': f'Error al ejecutar el comando: {str(cmd_error)}',
                    'output': out.getvalue(),
                    'errors': err.getvalue()
                }, status=500)
            
        except Exception as e:
            logger.error(f"Error en GenerarDatosPruebaView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error al generar datos: {str(e)}'
            }, status=500)

