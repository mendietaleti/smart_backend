from django.db import models
from django.conf import settings
from productos.models import Producto
from autenticacion_usuarios.models import Cliente

class Carrito(models.Model):
    id_carrito = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True, db_column='id_cliente')
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'carrito'
        verbose_name = 'Carrito de Compras'
        verbose_name_plural = 'Carritos de Compras'

    def __str__(self):
        if self.cliente:
            return f"Carrito de {self.cliente.id.nombre}"
        return f"Carrito (sesión: {self.session_key[:5]}...)"

    def get_total_items(self):
        return self.items.aggregate(total_cantidad=models.Sum('cantidad'))['total_cantidad'] or 0

    def get_total_precio(self):
        total = sum(item.get_subtotal() for item in self.items.all())
        return total

class ItemCarrito(models.Model):
    id_item = models.AutoField(primary_key=True)
    carrito = models.ForeignKey(Carrito, related_name='items', on_delete=models.CASCADE, db_column='id_carrito')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='id_producto')
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_adicion = models.DateTimeField(auto_now_add=True, db_column='fecha_agregado')

    class Meta:
        db_table = 'item_carrito'
        verbose_name = 'Item del Carrito'
        verbose_name_plural = 'Items del Carrito'
        unique_together = ('carrito', 'producto') # Un producto por carrito

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en Carrito {self.carrito.id_carrito}"

    def get_subtotal(self):
        return self.cantidad * self.precio_unitario

class Venta(models.Model):
    """Modelo para registrar ventas"""
    id_venta = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, db_column='id_cliente')
    fecha_venta = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, default='pendiente')  # pendiente, completada, cancelada
    metodo_pago = models.CharField(max_length=50, default='stripe')  # SOLO stripe
    direccion_entrega = models.CharField(max_length=255, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'venta'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_venta']
    
    def __str__(self):
        return f"Venta #{self.id_venta} - {self.cliente.id.nombre} - ${self.total}"

class DetalleVenta(models.Model):
    """Modelo para detalles de venta"""
    id_detalle = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, related_name='detalles', on_delete=models.CASCADE, db_column='venta_id')
    # Alinear con DB: columna 'id_producto' sin FK real para evitar errores de borrado
    producto = models.ForeignKey(Producto, on_delete=models.DO_NOTHING, db_column='id_producto', db_constraint=False, null=True, blank=True)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'detalle_venta'
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'
    
    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} - ${self.subtotal}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal automáticamente
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)


# ==========================================================
# MODELOS PARA CU11, CU12, CU13
# ==========================================================

class MetodoPago(models.Model):
    """Modelo para métodos de pago disponibles"""
    id_mp = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)  # efectivo, tarjeta, transferencia, etc.
    
    class Meta:
        db_table = 'metodo_de_pago'
        verbose_name = 'Método de Pago'
        verbose_name_plural = 'Métodos de Pago'
    
    def __str__(self):
        return self.nombre


class PagoOnline(models.Model):
    """Modelo para pagos en línea (CU11)"""
    id_pago = models.AutoField(primary_key=True)
    venta = models.OneToOneField(Venta, on_delete=models.CASCADE, db_column='venta_id', related_name='pago_online')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, default='pendiente')  # pendiente, exitoso, fallido, rechazado
    referencia = models.CharField(max_length=100, unique=True, blank=True, null=True)  # Número de referencia de transacción
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_mp')
    datos_tarjeta_hash = models.CharField(max_length=255, blank=True, null=True)  # Hash de últimos 4 dígitos (seguridad)
    # Campos para Stripe
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True, unique=True)  # ID de sesión de Stripe
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)  # ID de PaymentIntent de Stripe
    
    class Meta:
        db_table = 'pago_online'
        verbose_name = 'Pago Online'
        verbose_name_plural = 'Pagos Online'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"Pago #{self.id_pago} - Venta #{self.venta.id_venta} - ${self.monto} - {self.estado}"


class Comprobante(models.Model):
    """Modelo para comprobantes de venta (CU12)"""
    TIPOS_COMPROBANTE = [
        ('factura', 'Factura'),
        ('recibo', 'Recibo'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
    ]
    
    ESTADOS_COMPROBANTE = [
        ('pendiente', 'Pendiente'),
        ('generado', 'Generado'),
        ('anulado', 'Anulado'),
    ]
    
    id_comprobante = models.AutoField(primary_key=True)
    venta = models.OneToOneField(Venta, on_delete=models.CASCADE, db_column='venta_id', related_name='comprobante')
    tipo = models.CharField(max_length=20, choices=TIPOS_COMPROBANTE, default='factura')
    nit = models.CharField(max_length=20, blank=True, null=True)  # NIT del cliente
    nro = models.CharField(max_length=50, unique=True, blank=True, null=True)  # Número de comprobante
    fecha_emision = models.DateTimeField(auto_now_add=True)
    pdf_ruta = models.CharField(max_length=500, blank=True, null=True)  # Ruta al archivo PDF
    estado = models.CharField(max_length=20, choices=ESTADOS_COMPROBANTE, default='pendiente')
    total_factura = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'comprobante'
        verbose_name = 'Comprobante'
        verbose_name_plural = 'Comprobantes'
        ordering = ['-fecha_emision']
    
    def __str__(self):
        return f"{self.get_tipo_display()} #{self.nro or self.id_comprobante} - Venta #{self.venta.id_venta}"


class VentaHistorico(models.Model):
    """Modelo para historial agregado de ventas (CU13)"""
    id_his = models.AutoField(primary_key=True)
    fecha = models.DateField()
    cantidad_total = models.IntegerField(default=0)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    categoria = models.ForeignKey('productos.Categoria', on_delete=models.SET_NULL, null=True, blank=True, db_column='id_categoria')
    ventas_count = models.IntegerField(default=0)  # Número de ventas en este período
    
    class Meta:
        db_table = 'venta_historico'
        verbose_name = 'Historial de Venta'
        verbose_name_plural = 'Historial de Ventas'
        ordering = ['-fecha']
        unique_together = ('fecha', 'categoria')  # Un registro por fecha y categoría
    
    def __str__(self):
        cat = self.categoria.nombre if self.categoria else "General"
        return f"Historial {self.fecha} - {cat} - {self.ventas_count} ventas - ${self.monto_total}"