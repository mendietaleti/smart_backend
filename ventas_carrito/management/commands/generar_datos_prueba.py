"""
Comando para generar datos de prueba para el sistema SmartSales365
Genera categorías, productos, clientes y ventas históricas de los últimos 2 meses
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
import random

from productos.models import Categoria, Producto, Marca, Proveedor, Stock
from autenticacion_usuarios.models import Usuario, Rol, Cliente
from ventas_carrito.models import Venta, DetalleVenta


class Command(BaseCommand):
    help = 'Genera datos de prueba: categorías, productos, clientes y ventas históricas (2 meses)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ventas',
            type=int,
            default=120,
            help='Número de ventas a generar (default: 120)'
        )
        parser.add_argument(
            '--productos',
            type=int,
            default=25,
            help='Número de productos a generar (default: 25)'
        )
        parser.add_argument(
            '--clientes',
            type=int,
            default=12,
            help='Número de clientes a generar (default: 12)'
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Eliminar datos existentes antes de generar (CUIDADO: borra todo)'
        )

    def handle(self, *args, **options):
        num_ventas = options['ventas']
        num_productos = options['productos']
        num_clientes = options['clientes']
        limpiar = options['limpiar']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Generando datos de prueba para SmartSales365'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        try:
            with transaction.atomic():
                if limpiar:
                    self.stdout.write(self.style.WARNING('⚠️  LIMPIANDO datos existentes...'))
                    self._limpiar_datos()
                
                # 1. Crear categorías
                self.stdout.write('\n📁 Creando categorías...')
                categorias = self._crear_categorias()
                
                # 2. Crear marcas y proveedores
                self.stdout.write('\n🏷️  Creando marcas y proveedores...')
                marcas = self._crear_marcas()
                proveedores = self._crear_proveedores()
                
                # 3. Crear productos
                self.stdout.write(f'\n📦 Creando {num_productos} productos...')
                productos = self._crear_productos(categorias, marcas, proveedores, num_productos)
                
                # 4. Crear clientes
                self.stdout.write(f'\n👥 Creando {num_clientes} clientes...')
                clientes = self._crear_clientes(num_clientes)
                
                # 5. Crear ventas históricas (2 meses hacia atrás)
                self.stdout.write(f'\n💰 Creando {num_ventas} ventas históricas (últimos 2 meses)...')
                ventas_creadas = self._crear_ventas_historicas(clientes, productos, num_ventas)
                
                # Resumen
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write(self.style.SUCCESS('✅ DATOS GENERADOS EXITOSAMENTE'))
                self.stdout.write('=' * 60)
                self.stdout.write(f'📁 Categorías: {len(categorias)}')
                self.stdout.write(f'🏷️  Marcas: {len(marcas)}')
                self.stdout.write(f'🏢 Proveedores: {len(proveedores)}')
                self.stdout.write(f'📦 Productos: {len(productos)}')
                self.stdout.write(f'👥 Clientes: {len(clientes)}')
                self.stdout.write(f'💰 Ventas: {ventas_creadas}')
                self.stdout.write('=' * 60)
                
                # Información importante para el usuario
                self.stdout.write(self.style.SUCCESS('\n📝 INFORMACIÓN IMPORTANTE:'))
                self.stdout.write('=' * 60)
                self.stdout.write('🔑 Para iniciar sesión como cliente:')
                self.stdout.write('   Email: [cualquiera de los emails mostrados arriba]')
                self.stdout.write('   Contraseña: cliente123')
                self.stdout.write('')
                self.stdout.write('💡 Ejemplo de emails generados:')
                self.stdout.write('   - juan.garcia0@email.com')
                self.stdout.write('   - maria.rodriguez1@email.com')
                self.stdout.write('   - carlos.lopez2@email.com')
                self.stdout.write('   ...')
                self.stdout.write('')
                self.stdout.write('✅ Los clientes pueden:')
                self.stdout.write('   - Ver su historial de compras')
                self.stdout.write('   - Generar reportes de sus compras (PDF/Excel)')
                self.stdout.write('   - Ver notificaciones')
                self.stdout.write('=' * 60)
                self.stdout.write(self.style.SUCCESS('\n✨ Los datos están listos para usar!'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error generando datos: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise

    def _limpiar_datos(self):
        """Eliminar datos existentes (solo para desarrollo)"""
        DetalleVenta.objects.all().delete()
        Venta.objects.all().delete()
        Stock.objects.all().delete()
        Producto.objects.all().delete()
        Cliente.objects.all().delete()
        Usuario.objects.filter(id_rol__nombre='Cliente').delete()
        self.stdout.write(self.style.WARNING('  Datos eliminados'))

    def _crear_categorias(self):
        """Crear categorías de electrodomésticos"""
        categorias_data = [
            {'nombre': 'Cocina', 'descripcion': 'Electrodomésticos para la cocina'},
            {'nombre': 'Hogar', 'descripcion': 'Artículos para el hogar'},
            {'nombre': 'Deportes', 'descripcion': 'Equipos y accesorios deportivos'},
            {'nombre': 'Refrigeradores', 'descripcion': 'Refrigeradores y congeladores'},
            {'nombre': 'Lavadoras', 'descripcion': 'Lavadoras y secadoras'},
            {'nombre': 'Microondas', 'descripcion': 'Hornos microondas'},
            {'nombre': 'Aires Acondicionados', 'descripcion': 'Sistemas de aire acondicionado'},
            {'nombre': 'Televisores', 'descripcion': 'Televisores y monitores'},
            {'nombre': 'Audio y Sonido', 'descripcion': 'Equipos de audio y sonido'},
        ]
        
        categorias = []
        for cat_data in categorias_data:
            categoria, created = Categoria.objects.get_or_create(
                nombre=cat_data['nombre'],
                defaults={'descripcion': cat_data['descripcion']}
            )
            categorias.append(categoria)
            if created:
                self.stdout.write(f'  ✅ Creada: {categoria.nombre}')
            else:
                self.stdout.write(f'  ℹ️  Existente: {categoria.nombre}')
        
        return categorias

    def _crear_marcas(self):
        """Crear marcas de electrodomésticos"""
        marcas_nombres = [
            'Samsung', 'LG', 'Whirlpool', 'Mabe', 'Electrolux',
            'Panasonic', 'Sony', 'Philips', 'Bosch', 'Frigidaire', 'Oster', 'KitchenAid'
        ]
        
        marcas = []
        for nombre in marcas_nombres:
            marca, created = Marca.objects.get_or_create(nombre=nombre)
            marcas.append(marca)
            if created:
                self.stdout.write(f'  ✅ Marca creada: {marca.nombre}')
        
        return marcas

    def _crear_proveedores(self):
        """Crear proveedores"""
        proveedores_data = [
            {
                'nombre': 'ElectroHome Distribuidora',
                'telefono': '+591-2-1234567',
                'email': 'contacto@electrohome.com',
                'direccion': 'Av. Principal 123, La Paz'
            },
            {
                'nombre': 'TechSupply Bolivia',
                'telefono': '+591-2-2345678',
                'email': 'ventas@techsupply.bo',
                'direccion': 'Calle Comercio 456, Santa Cruz'
            },
            {
                'nombre': 'ElectroMundo S.A.',
                'telefono': '+591-2-3456789',
                'email': 'info@electromundo.bo',
                'direccion': 'Av. Libertad 789, Cochabamba'
            }
        ]
        
        proveedores = []
        for prov_data in proveedores_data:
            proveedor, created = Proveedor.objects.get_or_create(
                nombre=prov_data['nombre'],
                defaults=prov_data
            )
            proveedores.append(proveedor)
        
        return proveedores

    def _crear_productos(self, categorias, marcas, proveedores, num_productos):
        """Crear productos de electrodomésticos"""
        productos_data = [
            # Refrigeradores
            {'nombre': 'Refrigerador Samsung RT38K5982S8', 'precio': 4599.00, 'categoria': 'Refrigeradores', 'marca': 'Samsung'},
            {'nombre': 'Refrigerador LG GMX2055D', 'precio': 3899.00, 'categoria': 'Refrigeradores', 'marca': 'LG'},
            {'nombre': 'Refrigerador Mabe RMT2150', 'precio': 3299.00, 'categoria': 'Refrigeradores', 'marca': 'Mabe'},
            {'nombre': 'Refrigerador Whirlpool WRM45B', 'precio': 4199.00, 'categoria': 'Refrigeradores', 'marca': 'Whirlpool'},
            
            # Lavadoras
            {'nombre': 'Lavadora Samsung WW90T554DAW', 'precio': 3499.00, 'categoria': 'Lavadoras', 'marca': 'Samsung'},
            {'nombre': 'Lavadora LG WM3900HWA', 'precio': 3799.00, 'categoria': 'Lavadoras', 'marca': 'LG'},
            {'nombre': 'Lavadora Mabe LMA75X', 'precio': 2899.00, 'categoria': 'Lavadoras', 'marca': 'Mabe'},
            {'nombre': 'Lavadora Electrolux EWF1042A', 'precio': 3199.00, 'categoria': 'Lavadoras', 'marca': 'Electrolux'},
            
            # Microondas
            {'nombre': 'Microondas Samsung ME83KRW', 'precio': 899.00, 'categoria': 'Microondas', 'marca': 'Samsung'},
            {'nombre': 'Microondas LG MS3296DS', 'precio': 799.00, 'categoria': 'Microondas', 'marca': 'LG'},
            {'nombre': 'Microondas Panasonic NN-ST45KW', 'precio': 1099.00, 'categoria': 'Microondas', 'marca': 'Panasonic'},
            
            # Cocina
            {'nombre': 'Horno Eléctrico Whirlpool WOS51EC', 'precio': 1899.00, 'categoria': 'Cocina', 'marca': 'Whirlpool'},
            {'nombre': 'Cocina a Gas Mabe GMG7520', 'precio': 2499.00, 'categoria': 'Cocina', 'marca': 'Mabe'},
            {'nombre': 'Campana Extractora Bosch DWP64BC50', 'precio': 1299.00, 'categoria': 'Cocina', 'marca': 'Bosch'},
            {'nombre': 'Licuadora Oster BLSTBG-C00', 'precio': 599.00, 'categoria': 'Cocina', 'marca': 'Oster'},
            {'nombre': 'Batidora KitchenAid KSM150PS', 'precio': 1499.00, 'categoria': 'Cocina', 'marca': 'KitchenAid'},
            
            # Aires Acondicionados
            {'nombre': 'Aire Acondicionado Samsung AR12TXH', 'precio': 3299.00, 'categoria': 'Aires Acondicionados', 'marca': 'Samsung'},
            {'nombre': 'Aire Acondicionado LG DUALCOOL', 'precio': 3599.00, 'categoria': 'Aires Acondicionados', 'marca': 'LG'},
            {'nombre': 'Aire Acondicionado Mabe MSA12', 'precio': 2899.00, 'categoria': 'Aires Acondicionados', 'marca': 'Mabe'},
            
            # Televisores
            {'nombre': 'Smart TV Samsung 55" QLED', 'precio': 5999.00, 'categoria': 'Televisores', 'marca': 'Samsung'},
            {'nombre': 'Smart TV LG 50" 4K', 'precio': 4499.00, 'categoria': 'Televisores', 'marca': 'LG'},
            {'nombre': 'Smart TV Sony 43" 4K', 'precio': 3999.00, 'categoria': 'Televisores', 'marca': 'Sony'},
            
            # Audio y Sonido
            {'nombre': 'Sistema de Sonido Samsung HW-Q600C', 'precio': 1999.00, 'categoria': 'Audio y Sonido', 'marca': 'Samsung'},
            {'nombre': 'Barra de Sonido LG SN4', 'precio': 1499.00, 'categoria': 'Audio y Sonido', 'marca': 'LG'},
            {'nombre': 'Parlante Bluetooth Sony SRS-XB43', 'precio': 899.00, 'categoria': 'Audio y Sonido', 'marca': 'Sony'},
            
            # Hogar
            {'nombre': 'Aspiradora Electrolux Ergorapido', 'precio': 1299.00, 'categoria': 'Hogar', 'marca': 'Electrolux'},
            {'nombre': 'Plancha a Vapor Philips GC5030', 'precio': 599.00, 'categoria': 'Hogar', 'marca': 'Philips'},
            {'nombre': 'Ventilador de Torre Mabe VTM50', 'precio': 499.00, 'categoria': 'Hogar', 'marca': 'Mabe'},
        ]
        
        productos_creados = []
        productos_a_crear = productos_data[:num_productos] if num_productos <= len(productos_data) else productos_data
        
        for prod_data in productos_a_crear:
            # Buscar categoría
            categoria = next((c for c in categorias if c.nombre == prod_data['categoria']), categorias[0])
            # Buscar marca (crear si no existe)
            marca = next((m for m in marcas if m.nombre == prod_data['marca']), None)
            if not marca:
                marca, _ = Marca.objects.get_or_create(nombre=prod_data['marca'])
                marcas.append(marca)
            # Proveedor aleatorio
            proveedor = random.choice(proveedores)
            
            producto, created = Producto.objects.get_or_create(
                nombre=prod_data['nombre'],
                defaults={
                    'descripcion': f'{prod_data["nombre"]} - Electrodoméstico de calidad',
                    'precio': prod_data['precio'],
                    'precio_compra': prod_data['precio'] * 0.7,  # 70% del precio de venta
                    'categoria': categoria,
                    'marca': marca,
                    'proveedor': proveedor,
                    'imagen': f'https://images.unsplash.com/photo-{random.randint(1500000000000, 1600000000000)}?w=400&h=300&fit=crop'
                }
            )
            
            # Crear stock
            if created:
                Stock.objects.get_or_create(
                    producto=producto,
                    defaults={'cantidad': random.randint(5, 50)}
                )
            
            productos_creados.append(producto)
        
        return productos_creados

    def _crear_clientes(self, num_clientes):
        """Crear clientes de prueba"""
        nombres = [
            'Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Laura', 'Pedro', 'Carmen',
            'Roberto', 'Patricia', 'Fernando', 'Sofía', 'Miguel', 'Isabel', 'Diego'
        ]
        apellidos = [
            'García', 'Rodríguez', 'López', 'Martínez', 'González', 'Pérez', 'Sánchez',
            'Ramírez', 'Torres', 'Flores', 'Rivera', 'Gómez', 'Díaz', 'Cruz', 'Morales'
        ]
        ciudades = ['La Paz', 'Santa Cruz', 'Cochabamba', 'Sucre', 'Oruro', 'Tarija', 'Potosí']
        
        # Asegurar que existe el rol Cliente
        rol_cliente, _ = Rol.objects.get_or_create(nombre='Cliente')
        
        clientes = []
        clientes_info = []  # Para mostrar credenciales al final
        
        for i in range(num_clientes):
            nombre = random.choice(nombres)
            apellido = random.choice(apellidos)
            email = f'{nombre.lower()}.{apellido.lower()}{i}@email.com'
            password = 'cliente123'  # Contraseña estándar para todos los clientes de prueba
            
            # Verificar si el cliente ya existe
            if Usuario.objects.filter(email=email).exists():
                usuario = Usuario.objects.get(email=email)
                # Asegurar que tenga la contraseña correcta
                if not usuario.check_password(password):
                    usuario.set_password(password)
                    usuario.save()
                try:
                    cliente = Cliente.objects.get(id=usuario)
                    clientes.append(cliente)
                    clientes_info.append({
                        'email': email,
                        'password': password,
                        'nombre': f'{nombre} {apellido}',
                        'existe': True
                    })
                    continue
                except Cliente.DoesNotExist:
                    pass
            else:
                # Crear usuario
                usuario = Usuario.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    email=email,
                    telefono=f'+591-7{random.randint(1000000, 9999999)}',
                    id_rol=rol_cliente,
                    estado=True
                )
                usuario.set_password(password)
                usuario.save()
            
            # Crear cliente
            cliente, created = Cliente.objects.get_or_create(
                id=usuario,
                defaults={
                    'direccion': f'Calle {random.randint(1, 100)} #{random.randint(1, 500)}',
                    'ciudad': random.choice(ciudades)
                }
            )
            clientes.append(cliente)
            clientes_info.append({
                'email': email,
                'password': password,
                'nombre': f'{nombre} {apellido}',
                'existe': False
            })
        
        # Mostrar credenciales de los clientes creados
        self.stdout.write('\n📋 CREDENCIALES DE CLIENTES CREADOS:')
        self.stdout.write('=' * 60)
        for info in clientes_info[:5]:  # Mostrar solo los primeros 5
            estado = '✅ Nuevo' if not info['existe'] else 'ℹ️  Existente'
            self.stdout.write(f'{estado} - {info["nombre"]}')
            self.stdout.write(f'   Email: {info["email"]}')
            self.stdout.write(f'   Contraseña: {info["password"]}')
            self.stdout.write('')
        
        if len(clientes_info) > 5:
            self.stdout.write(f'   ... y {len(clientes_info) - 5} clientes más')
            self.stdout.write('   (Todos usan la misma contraseña: cliente123)')
        
        self.stdout.write('=' * 60)
        
        return clientes

    def _crear_ventas_historicas(self, clientes, productos, num_ventas):
        """Crear ventas históricas distribuidas en los últimos 2 meses"""
        ahora = timezone.now()
        fecha_inicio = ahora - timedelta(days=60)  # Hace 2 meses
        fecha_fin = ahora  # Hoy
        
        # El sistema SOLO usa Stripe para pagos
        metodos_pago = ['stripe']  # TODAS las ventas con Stripe
        estados = ['completada', 'completada', 'completada', 'completada', 'pendiente']  # Mayoría completadas
        
        ventas_creadas = 0
        
        for i in range(num_ventas):
            # Fecha aleatoria en los últimos 2 meses
            dias_aleatorios = random.randint(0, 60)
            fecha_venta = fecha_inicio + timedelta(days=dias_aleatorios)
            
            # Hora aleatoria durante el día (9 AM - 9 PM)
            hora = random.randint(9, 21)
            minuto = random.randint(0, 59)
            segundo = random.randint(0, 59)
            fecha_venta = fecha_venta.replace(hour=hora, minute=minuto, second=segundo)
            
            # Cliente aleatorio
            cliente = random.choice(clientes)
            
            # Productos aleatorios (1-4 productos por venta)
            num_productos_venta = random.randint(1, 4)
            productos_venta = random.sample(productos, min(num_productos_venta, len(productos)))
            
            # Calcular total
            total = 0
            detalles_data = []
            
            for producto in productos_venta:
                cantidad = random.randint(1, 3)
                precio_unitario = producto.precio
                subtotal = cantidad * precio_unitario
                total += subtotal
                
                detalles_data.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal
                })
            
            # Crear venta (auto_now_add establecerá fecha actual, luego la actualizamos)
            venta = Venta.objects.create(
                cliente=cliente,
                total=total,
                estado=random.choice(estados),
                metodo_pago=random.choice(metodos_pago),
                direccion_entrega=cliente.direccion,
                notas=f'Venta generada automáticamente - {fecha_venta.strftime("%d/%m/%Y %H:%M")}'
            )
            # Actualizar fecha a la fecha histórica específica
            Venta.objects.filter(id_venta=venta.id_venta).update(fecha_venta=fecha_venta)
            # Refrescar el objeto para tener la fecha actualizada
            venta.refresh_from_db()
            
            # Crear detalles de venta
            for detalle_data in detalles_data:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=detalle_data['producto'],
                    cantidad=detalle_data['cantidad'],
                    precio_unitario=detalle_data['precio_unitario'],
                    subtotal=detalle_data['subtotal']
                )
            
            ventas_creadas += 1
            
            if (i + 1) % 20 == 0:
                self.stdout.write(f'  ✅ {i + 1}/{num_ventas} ventas creadas...')
        
        return ventas_creadas

