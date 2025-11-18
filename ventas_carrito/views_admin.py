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
    Endpoint administrativo para generar datos de prueba
    """
    
    allowed_origins = {
        'https://smart-frontend-blond.vercel.app',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    }
    
    def _add_cors_headers(self, response, request):
        origin = request.headers.get('Origin')
        if origin:
            if origin in self.allowed_origins or origin.endswith('.vercel.app'):
                response['Access-Control-Allow-Origin'] = origin
            else:
                response['Access-Control-Allow-Origin'] = 'https://smart-frontend-blond.vercel.app'
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
        response['Vary'] = 'Origin'
        return response
    
    def options(self, request):
        response = JsonResponse({'success': True})
        return self._add_cors_headers(response, request)
    
    def get(self, request):
        """Método GET para verificar que el endpoint esté accesible"""
        response = JsonResponse({
            'success': True,
            'message': 'Endpoint de generar datos de prueba está disponible',
            'authenticated': request.session.get('is_authenticated', False)
        })
        return self._add_cors_headers(response, request)
    
    def post(self, request):
        # Verificar autenticación
        if not request.session.get('is_authenticated'):
            response = JsonResponse({
                'success': False,
                'message': 'Debe iniciar sesión'
            }, status=401)
            return self._add_cors_headers(response, request)
        
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
                
                response = JsonResponse({
                    'success': True,
                    'message': 'Datos generados correctamente',
                    'summary': summary,
                    'output': output,
                    'errors': errors if errors else None
                })
                return self._add_cors_headers(response, request)
                
            except Exception as cmd_error:
                logger.error(f"Error ejecutando comando generar_datos_prueba: {str(cmd_error)}", exc_info=True)
                response = JsonResponse({
                    'success': False,
                    'message': f'Error al ejecutar el comando: {str(cmd_error)}',
                    'output': out.getvalue(),
                    'errors': err.getvalue()
                }, status=500)
                return self._add_cors_headers(response, request)
            
        except Exception as e:
            logger.error(f"Error en GenerarDatosPruebaView: {str(e)}", exc_info=True)
            response = JsonResponse({
                'success': False,
                'message': f'Error al generar datos: {str(e)}'
            }, status=500)
            return self._add_cors_headers(response, request)

