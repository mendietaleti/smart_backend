"""
Comando para actualizar TODAS las ventas existentes a método de pago 'stripe'
"""
from django.core.management.base import BaseCommand
from ventas_carrito.models import Venta


class Command(BaseCommand):
    help = 'Actualiza TODAS las ventas existentes para que usen método de pago Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se actualizaría sin hacer cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Obtener todas las ventas que NO tienen 'stripe' como método de pago
        ventas_a_actualizar = Venta.objects.exclude(metodo_pago='stripe')
        total_ventas = ventas_a_actualizar.count()
        
        if total_ventas == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ Todas las ventas ya usan Stripe como método de pago')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] Se actualizarían {total_ventas} ventas a método de pago Stripe')
            )
            # Mostrar algunos ejemplos
            for venta in ventas_a_actualizar[:5]:
                self.stdout.write(
                    f'  - Venta #{venta.id_venta}: {venta.metodo_pago} → stripe'
                )
            if total_ventas > 5:
                self.stdout.write(f'  ... y {total_ventas - 5} más')
            return
        
        # Actualizar todas las ventas
        actualizadas = ventas_a_actualizar.update(metodo_pago='stripe')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Se actualizaron {actualizadas} ventas a método de pago Stripe'
            )
        )



