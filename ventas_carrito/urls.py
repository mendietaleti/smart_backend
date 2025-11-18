from django.urls import path
from . import views
from . import checkout_views
from . import pagos_views
from . import comprobantes_views
from . import historial_views
from . import stripe_views
from . import views_admin

app_name = 'ventas_carrito'

urlpatterns = [
    path('carrito/', views.CarritoView.as_view(), name='carrito'),
    path('carrito/management/', views.CarritoManagementView.as_view(), name='carrito_management'),
    path('checkout/', checkout_views.CheckoutView.as_view(), name='checkout'),
    # CU11: Pagos en línea
    path('pagos-online/', pagos_views.PagoOnlineView.as_view(), name='pagos_online'),
    path('pagos-online/<int:pago_id>/', pagos_views.EstadoPagoView.as_view(), name='estado_pago'),
    # Stripe Payment Intents (pago en la misma página)
    path('stripe/publishable-key/', stripe_views.GetStripePublishableKeyView.as_view(), name='stripe_publishable_key'),
    path('stripe/create-payment-intent/', stripe_views.CreatePaymentIntentView.as_view(), name='stripe_create_payment_intent'),
    path('stripe/verify-payment-intent/', stripe_views.VerifyPaymentIntentView.as_view(), name='stripe_verify_payment_intent'),
    # CU12: Comprobantes
    path('comprobantes/', comprobantes_views.ComprobanteView.as_view(), name='comprobantes'),
    path('comprobantes/generar/', comprobantes_views.ComprobanteView.as_view(), name='generar_comprobante'),
    path('comprobantes/<int:venta_id>/', comprobantes_views.ComprobanteView.as_view(), name='comprobante_detail'),
    path('comprobantes/<int:venta_id>/pdf/', comprobantes_views.ComprobantePDFView.as_view(), name='comprobante_pdf'),
    path('comprobantes/<int:venta_id>/excel/', comprobantes_views.ComprobanteExcelView.as_view(), name='comprobante_excel'),
    # CU13: Historial de ventas
    path('historial/', historial_views.HistorialVentasView.as_view(), name='historial_ventas'),
    path('historial/filtros/', historial_views.HistorialFiltrosView.as_view(), name='historial_filtros'),
    path('historial/agregado/', historial_views.HistorialAgregadoView.as_view(), name='historial_agregado'),
    path('historial/sincronizar/', historial_views.SincronizarHistorialView.as_view(), name='sincronizar_historial'),
    path('dashboard/stats/', historial_views.DashboardStatsView.as_view(), name='dashboard_stats'),
    # Endpoint administrativo para generar datos de prueba
    path('admin/generar-datos-prueba/', views_admin.GenerarDatosPruebaView.as_view(), name='generar_datos_prueba'),
]