"""
Comando para listar clientes y sus credenciales de acceso
Útil para probar el sistema con cuentas de cliente
"""
from django.core.management.base import BaseCommand
from autenticacion_usuarios.models import Usuario, Rol, Cliente
from ventas_carrito.models import Venta


class Command(BaseCommand):
    help = 'Lista todos los clientes con sus credenciales y número de compras'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='cliente123',
            help='Contraseña estándar de los clientes (default: cliente123)'
        )

    def handle(self, *args, **options):
        password = options['password']
        
        try:
            # Obtener rol Cliente
            try:
                rol_cliente = Rol.objects.get(nombre='Cliente')
            except Rol.DoesNotExist:
                self.stdout.write(self.style.ERROR('❌ No existe el rol "Cliente"'))
                return
            
            # Obtener todos los clientes
            clientes = Cliente.objects.select_related('id', 'id__id_rol').all().order_by('id__nombre')
            
            if not clientes.exists():
                self.stdout.write(self.style.WARNING('⚠️  No hay clientes registrados'))
                self.stdout.write('   Ejecuta: python manage.py generar_datos_prueba')
                return
            
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('📋 LISTA DE CLIENTES Y CREDENCIALES'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write('')
            
            for cliente in clientes:
                usuario = cliente.id
                # Contar ventas del cliente
                num_ventas = Venta.objects.filter(cliente=cliente).count()
                
                self.stdout.write(f'👤 {usuario.nombre} {usuario.apellido or ""}'.strip())
                self.stdout.write(f'   📧 Email: {usuario.email}')
                self.stdout.write(f'   🔑 Contraseña: {password}')
                self.stdout.write(f'   📞 Teléfono: {usuario.telefono or "N/A"}')
                self.stdout.write(f'   📍 Ciudad: {cliente.ciudad or "N/A"}')
                self.stdout.write(f'   💰 Compras realizadas: {num_ventas}')
                self.stdout.write('')
            
            self.stdout.write('=' * 70)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Total de clientes: {clientes.count()}'))
            self.stdout.write('')
            self.stdout.write('💡 Para iniciar sesión, usa cualquier email de arriba con la contraseña mostrada')
            self.stdout.write('')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))




