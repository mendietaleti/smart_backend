"""
CU12: Generar Comprobante de Venta
"""
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from django.utils import timezone
import os
import json
import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from io import BytesIO

from .models import Venta, Comprobante, DetalleVenta
from autenticacion_usuarios.models import Usuario, Cliente, Bitacora

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ComprobanteView(View):
    """
    CU12: Generar Comprobante de Venta
    """
    
    def get(self, request, venta_id=None):
        """Obtener o generar comprobante"""
        if venta_id:
            return self._get_comprobante(request, venta_id)
        else:
            return JsonResponse({
                'endpoint': 'Comprobante API',
                'description': 'Generar y obtener comprobantes de venta',
                'endpoints': {
                    'GET /api/ventas/comprobantes/{venta_id}/': 'Obtener comprobante',
                    'GET /api/ventas/comprobantes/{venta_id}/pdf/': 'Descargar PDF',
                    'POST /api/ventas/comprobantes/generar/': 'Generar comprobante'
                }
            })
    
    def post(self, request):
        """Generar comprobante para una venta"""
        try:
            data = json.loads(request.body)
            venta_id = data.get('venta_id')
            
            if not venta_id:
                return JsonResponse({
                    'success': False,
                    'message': 'ID de venta requerido'
                }, status=400)
            
            # Obtener venta
            try:
                venta = Venta.objects.select_related('cliente', 'cliente__id').prefetch_related('detalles', 'detalles__producto').get(id_venta=venta_id)
            except Venta.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Venta no encontrada'
                }, status=404)
            
            # Verificar que la venta esté completada
            if venta.estado != 'completada':
                return JsonResponse({
                    'success': False,
                    'message': 'La venta debe estar completada para generar comprobante'
                }, status=400)
            
            # Verificar si ya existe comprobante
            if hasattr(venta, 'comprobante'):
                comprobante = venta.comprobante
                # Regenerar PDF con el nuevo diseño mejorado
                try:
                    if comprobante.pdf_ruta:
                        old_filepath = os.path.join(settings.MEDIA_ROOT, comprobante.pdf_ruta)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                except:
                    pass
                # Regenerar PDF con diseño mejorado
                pdf_path = self._generar_pdf(comprobante, venta)
                comprobante.pdf_ruta = pdf_path
                comprobante.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Comprobante regenerado con nuevo diseño',
                    'comprobante': {
                        'id': comprobante.id_comprobante,
                        'numero': comprobante.nro,
                        'tipo': comprobante.tipo,
                        'fecha': comprobante.fecha_emision.isoformat(),
                        'pdf_url': f'/api/ventas/comprobantes/{venta_id}/pdf/'
                    }
                }, status=200)
            
            # Generar comprobante
            comprobante = self._generar_comprobante(venta, data.get('tipo', 'factura'))
            
            return JsonResponse({
                'success': True,
                'message': 'Comprobante generado exitosamente',
                'comprobante': {
                    'id': comprobante.id_comprobante,
                    'numero': comprobante.nro,
                    'tipo': comprobante.tipo,
                    'fecha': comprobante.fecha_emision.isoformat(),
                    'pdf_url': f'/api/ventas/comprobantes/{venta_id}/pdf/'
                }
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Formato de datos inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en ComprobanteView.post: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _get_comprobante(self, request, venta_id):
        """Obtener información del comprobante"""
        try:
            venta = Venta.objects.get(id_venta=venta_id)
            
            if not hasattr(venta, 'comprobante'):
                return JsonResponse({
                    'success': False,
                    'message': 'Comprobante no encontrado'
                }, status=404)
            
            comprobante = venta.comprobante
            
            # Si el PDF existe pero queremos regenerarlo, forzar regeneración
            regenerar = request.GET.get('regenerar', 'false').lower() == 'true'
            if regenerar:
                try:
                    # Eliminar PDF anterior si existe
                    if comprobante.pdf_ruta:
                        old_filepath = os.path.join(settings.MEDIA_ROOT, comprobante.pdf_ruta)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    
                    # Regenerar PDF con nuevo diseño
                    pdf_path = self._generar_pdf(comprobante, venta)
                    comprobante.pdf_ruta = pdf_path
                    comprobante.save()
                except Exception as e:
                    logger.warning(f"No se pudo regenerar PDF: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'comprobante': {
                    'id': comprobante.id_comprobante,
                    'numero': comprobante.nro,
                    'tipo': comprobante.tipo,
                    'nit': comprobante.nit,
                    'fecha': comprobante.fecha_emision.isoformat(),
                    'total': float(comprobante.total_factura),
                    'estado': comprobante.estado,
                    'pdf_url': f'/api/ventas/comprobantes/{venta_id}/pdf/'
                }
            }, status=200)
            
        except Venta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Venta no encontrada'
            }, status=404)
        except Exception as e:
            logger.error(f"Error en ComprobanteView._get_comprobante: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)
    
    def _generar_comprobante(self, venta, tipo='factura'):
        """Generar comprobante y PDF"""
        # Generar número de comprobante
        numero = self._generar_numero_comprobante(tipo)
        
        # Crear comprobante
        comprobante = Comprobante.objects.create(
            venta=venta,
            tipo=tipo,
            nro=numero,
            nit=venta.cliente.id.email if hasattr(venta.cliente.id, 'email') else None,
            total_factura=venta.total,
            estado='generado'
        )
        
        # Generar PDF
        pdf_path = self._generar_pdf(comprobante, venta)
        comprobante.pdf_ruta = pdf_path
        comprobante.save()
        
        return comprobante
    
    def _generar_numero_comprobante(self, tipo):
        """Generar número único de comprobante"""
        prefijo = {
            'factura': 'FAC',
            'recibo': 'REC',
            'nota_credito': 'NC',
            'nota_debito': 'ND'
        }.get(tipo, 'COM')
        
        timestamp = timezone.now().strftime('%Y%m%d')
        numero_secuencial = Comprobante.objects.filter(tipo=tipo).count() + 1
        return f"{prefijo}-{timestamp}-{numero_secuencial:05d}"
    
    def _generar_pdf(self, comprobante, venta):
        """Generar archivo PDF del comprobante con diseño mejorado"""
        # Crear directorio de comprobantes si no existe
        comprobantes_dir = os.path.join(settings.MEDIA_ROOT, 'comprobantes')
        os.makedirs(comprobantes_dir, exist_ok=True)
        
        # Nombre del archivo
        filename = f"comprobante_{comprobante.id_comprobante}.pdf"
        filepath = os.path.join(comprobantes_dir, filename)
        
        # Crear documento PDF
        doc = SimpleDocTemplate(filepath, pagesize=A4, 
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        story = []
        
        # Colores personalizados
        color_primary = colors.HexColor('#2563eb')  # Azul moderno
        color_secondary = colors.HexColor('#1e40af')  # Azul oscuro
        color_accent = colors.HexColor('#3b82f6')  # Azul claro
        color_bg = colors.HexColor('#f8fafc')  # Gris muy claro
        color_text = colors.HexColor('#1e293b')  # Gris oscuro
        color_border = colors.HexColor('#e2e8f0')  # Gris claro
        
        # Estilos personalizados
        styles = getSampleStyleSheet()
        
        # Estilo para título principal
        title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=color_primary,
            spaceAfter=20,
            alignment=1,  # Centrado
            fontName='Helvetica-Bold',
            leading=34
        )
        
        # Estilo para subtítulos
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=color_text,
            spaceAfter=12,
            fontName='Helvetica-Bold',
            leading=18
        )
        
        # Estilo para texto normal
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=color_text,
            leading=14,
            fontName='Helvetica'
        )
        
        # Estilo para texto pequeño
        small_style = ParagraphStyle(
            'SmallStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            leading=12,
            fontName='Helvetica'
        )
        
        # HEADER CON FONDO
        header_data = [
            [
                Paragraph(
                    '<font size="32" color="#2563eb"><b>SmartSales365</b></font><br/>'
                    '<font size="10" color="#64748b">Sistema Inteligente de Ventas</font>',
                    ParagraphStyle(
                        'HeaderLeft',
                        fontSize=12,
                        textColor=color_text,
                        fontName='Helvetica-Bold',
                        leading=16
                    )
                ),
                Paragraph(
                    f'<font size="24" color="#2563eb"><b>{comprobante.get_tipo_display().upper()}</b></font><br/>'
                    f'<font size="10" color="#64748b">N° {comprobante.nro}</font>',
                    ParagraphStyle(
                        'HeaderRight',
                        fontSize=12,
                        textColor=color_text,
                        alignment=2,  # Derecha
                        fontName='Helvetica-Bold',
                        leading=16
                    )
                )
            ]
        ]
        
        header_table = Table(header_data, colWidths=[4*inch, 2.5*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_bg),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMBORDER', (0, 0), (-1, -1), 2, color_primary),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.4*inch))
        
        # INFORMACIÓN DE EMPRESA Y CLIENTE (Lado a lado)
        cliente = venta.cliente.id
        
        empresa_info = [
            [Paragraph('<b>EMPRESA</b>', subtitle_style)],
            [Paragraph('SmartSales365', normal_style)],
            [Paragraph('NIT: 12345678-9', small_style)],
            [Paragraph('Ciudad, País', small_style)],
            [Paragraph('Tel: +123 456 7890', small_style)],
            [Paragraph('Email: contacto@smartsales365.com', small_style)],
        ]
        
        cliente_info = [
            [Paragraph('<b>CLIENTE</b>', subtitle_style)],
            [Paragraph(f"{cliente.nombre} {cliente.apellido or ''}".strip(), normal_style)],
            [Paragraph(f"NIT/CI: {comprobante.nit or 'N/A'}", small_style)],
            [Paragraph(f"Email: {cliente.email}", small_style)],
            [Paragraph(f"Tel: {cliente.telefono or 'N/A'}", small_style)],
        ]

        # Obtener dirección del cliente o de la venta
        direccion = venta.direccion_entrega
        if not direccion:
            direccion = f"{venta.cliente.direccion or ''}, {venta.cliente.ciudad or ''}".strip() or "N/A"

        cliente_info.append(
            [Paragraph(f"Dirección: {direccion}", small_style)]
        )
        
        info_data = [
            [
                Table(empresa_info, colWidths=[3*inch]),
                Table(cliente_info, colWidths=[3*inch])
            ]
        ]
        
        info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # INFORMACIÓN DEL COMPROBANTE
        comprobante_info = [
            [
                Paragraph('<b>Fecha de Emisión:</b>', normal_style),
                Paragraph(comprobante.fecha_emision.strftime('%d/%m/%Y %H:%M'), normal_style),
                Paragraph('<b>Método de Pago:</b>', normal_style),
                Paragraph(venta.metodo_pago.replace('_', ' ').title(), normal_style),
            ]
        ]
        
        comprobante_table = Table(comprobante_info, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        comprobante_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_bg),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'LEFT'),
            ('ALIGN', (3, 0), (3, 0), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMBORDER', (0, 0), (-1, -1), 1, color_border),
        ]))
        story.append(comprobante_table)
        story.append(Spacer(1, 0.3*inch))
        
        # TABLA DE PRODUCTOS MEJORADA
        detalles = venta.detalles.all()
        detalles_data = [
            [
                Paragraph('<b>PRODUCTO</b>', ParagraphStyle('Header', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)),
                Paragraph('<b>CANT.</b>', ParagraphStyle('Header', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)),
                Paragraph('<b>PRECIO UNIT.</b>', ParagraphStyle('Header', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)),
                Paragraph('<b>SUBTOTAL</b>', ParagraphStyle('Header', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)),
            ]
        ]
        
        for detalle in detalles:
            producto_nombre = detalle.producto.nombre if detalle.producto else f"Producto #{detalle.producto_id}"
            detalles_data.append([
                Paragraph(producto_nombre, normal_style),
                Paragraph(str(detalle.cantidad), ParagraphStyle('Normal', fontSize=10, textColor=color_text, alignment=1)),
                Paragraph(f"${detalle.precio_unitario:.2f}", ParagraphStyle('Normal', fontSize=10, textColor=color_text, alignment=2)),
                Paragraph(f"${detalle.subtotal:.2f}", ParagraphStyle('Normal', fontSize=10, textColor=color_text, fontName='Helvetica-Bold', alignment=2)),
            ])
        
        detalles_table = Table(detalles_data, colWidths=[3.5*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        detalles_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), color_primary),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 14),
            ('TOPPADDING', (0, 0), (-1, 0), 14),
            # Filas de datos
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), color_text),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, color_border),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.white),
            # Alternar colores de filas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, color_bg]),
        ]))
        story.append(detalles_table)
        story.append(Spacer(1, 0.4*inch))
        
        # TOTALES CON DISEÑO MEJORADO
        subtotal = float(venta.total)  # Por ahora sin descuentos
        total_data = [
            [
                '',
                Paragraph('<b>SUBTOTAL:</b>', ParagraphStyle('Total', fontSize=11, textColor=color_text, fontName='Helvetica', alignment=2)),
                Paragraph(f'${subtotal:.2f}', ParagraphStyle('Total', fontSize=11, textColor=color_text, fontName='Helvetica', alignment=2)),
            ],
            [
                '',
                Paragraph('<b>TOTAL A PAGAR:</b>', ParagraphStyle('TotalFinal', fontSize=14, textColor=color_primary, fontName='Helvetica-Bold', alignment=2)),
                Paragraph(f'<font color="#2563eb"><b>${venta.total:.2f}</b></font>', ParagraphStyle('TotalFinal', fontSize=14, textColor=color_primary, fontName='Helvetica-Bold', alignment=2)),
            ]
        ]
        
        total_table = Table(total_data, colWidths=[3.5*inch, 1.5*inch, 1.7*inch])
        total_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
            ('FONTSIZE', (1, 0), (1, 0), 11),
            ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 1), (1, 1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPBORDER', (1, 1), (-1, 1), 2, color_primary),
            ('BACKGROUND', (1, 1), (-1, 1), color_bg),
        ]))
        story.append(total_table)
        story.append(Spacer(1, 0.4*inch))
        
        # NOTAS Y INFORMACIÓN ADICIONAL
        if venta.notas:
            notas_box = [
                [Paragraph('<b>NOTAS ADICIONALES:</b>', subtitle_style)],
                [Paragraph(venta.notas, normal_style)],
            ]
            notas_table = Table(notas_box, colWidths=[6.7*inch])
            notas_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), color_bg),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMBORDER', (0, 0), (-1, -1), 1, color_border),
            ]))
            story.append(notas_table)
            story.append(Spacer(1, 0.3*inch))
        
        # FOOTER
        footer_text = (
            '<font size="8" color="#94a3b8">'
            'Gracias por su compra. Este documento es válido como comprobante fiscal.<br/>'
            'SmartSales365 - Sistema Inteligente de Ventas | www.smartsales365.com'
            '</font>'
        )
        footer = Paragraph(footer_text, ParagraphStyle(
            'Footer',
            fontSize=8,
            textColor=colors.HexColor('#94a3b8'),
            alignment=1,  # Centrado
            fontName='Helvetica',
            leading=10
        ))
        story.append(Spacer(1, 0.3*inch))
        story.append(footer)
        
        # Construir PDF
        doc.build(story)
        
        # Retornar ruta relativa
        return os.path.join('comprobantes', filename)


@method_decorator(csrf_exempt, name='dispatch')
class ComprobantePDFView(View):
    """Descargar PDF del comprobante"""
    
    def get(self, request, venta_id):
        try:
            venta = Venta.objects.get(id_venta=venta_id)
            
            # Si no existe comprobante, generarlo automáticamente
            if not hasattr(venta, 'comprobante'):
                comprobante_view = ComprobanteView()
                comprobante = comprobante_view._generar_comprobante(venta, tipo='factura')
            else:
                comprobante = venta.comprobante
            
            # Siempre regenerar el PDF para asegurar el diseño mejorado
            comprobante_view = ComprobanteView()
            try:
                # Eliminar PDF anterior si existe
                if comprobante.pdf_ruta:
                    old_filepath = os.path.join(settings.MEDIA_ROOT, comprobante.pdf_ruta)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
            except Exception as e:
                logger.warning(f"Error al eliminar PDF anterior: {str(e)}")
            
            # Regenerar PDF con diseño mejorado usando el método de ComprobanteView
            pdf_path = comprobante_view._generar_pdf(comprobante, venta)
            comprobante.pdf_ruta = pdf_path
            comprobante.save()
            
            # Ruta completa del archivo
            filepath = os.path.join(settings.MEDIA_ROOT, pdf_path)
            
            if not os.path.exists(filepath):
                return JsonResponse({
                    'success': False,
                    'message': 'Archivo PDF no encontrado'
                }, status=404)
            
            # Leer el archivo y retornarlo
            with open(filepath, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="factura_{comprobante.nro}.pdf"'
                return response
            
        except Venta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Venta no encontrada'
            }, status=404)
        except Exception as e:
            logger.error(f"Error en ComprobantePDFView.get: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ComprobanteExcelView(View):
    """Descargar comprobante en formato Excel"""
    
    def get(self, request, venta_id):
        try:
            venta = Venta.objects.get(id_venta=venta_id)
            
            # Generar comprobante si no existe
            if not hasattr(venta, 'comprobante'):
                comprobante_view = ComprobanteView()
                comprobante = comprobante_view._generar_comprobante(venta, tipo='factura')
            else:
                comprobante = venta.comprobante
            
            # Crear workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Factura"
            
            # Estilos
            header_fill = PatternFill(start_color="0066FF", end_color="0066FF", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            title_font = Font(bold=True, size=16, color="0066FF")
            
            # Título
            ws['A1'] = f"{comprobante.get_tipo_display().upper()}"
            ws['A1'].font = title_font
            ws.merge_cells('A1:D1')
            ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[1].height = 30
            
            # Información de la empresa
            row = 3
            ws[f'A{row}'] = 'SmartSales365'
            ws[f'A{row}'].font = Font(bold=True, size=14)
            row += 1
            ws[f'A{row}'] = 'Sistema de Ventas Inteligente'
            row += 2
            
            # Información del comprobante
            ws[f'A{row}'] = f'Número: {comprobante.nro}'
            ws[f'A{row}'].font = Font(bold=True)
            row += 1
            ws[f'A{row}'] = f'Fecha: {comprobante.fecha_emision.strftime("%d/%m/%Y %H:%M:%S")}'
            row += 2
            
            # Información del cliente
            cliente = venta.cliente.id
            ws[f'A{row}'] = 'Cliente:'
            ws[f'A{row}'].font = Font(bold=True)
            row += 1
            ws[f'A{row}'] = f'{cliente.nombre} {cliente.apellido or ""}'.strip()
            row += 1
            ws[f'A{row}'] = f'Email: {cliente.email}'
            row += 1
            if cliente.telefono:
                ws[f'A{row}'] = f'Teléfono: {cliente.telefono}'
                row += 1
            if venta.cliente.direccion:
                ws[f'A{row}'] = f'Dirección: {venta.cliente.direccion}'
                row += 1
            row += 1
            
            # Tabla de productos
            ws[f'A{row}'] = 'Producto'
            ws[f'B{row}'] = 'Cantidad'
            ws[f'C{row}'] = 'Precio Unitario'
            ws[f'D{row}'] = 'Subtotal'
            
            # Aplicar estilo al encabezado
            for col in ['A', 'B', 'C', 'D']:
                cell = ws[f'{col}{row}']
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            row += 1
            
            # Detalles de venta
            detalles = venta.detalles.all()
            for detalle in detalles:
                ws[f'A{row}'] = detalle.producto.nombre if detalle.producto else f'Producto #{detalle.producto_id}'
                ws[f'B{row}'] = detalle.cantidad
                ws[f'C{row}'] = float(detalle.precio_unitario)
                ws[f'D{row}'] = float(detalle.subtotal)
                row += 1
            
            # Totales
            row += 1
            ws[f'C{row}'] = 'TOTAL:'
            ws[f'C{row}'].font = Font(bold=True, size=12)
            ws[f'D{row}'] = float(venta.total)
            ws[f'D{row}'].font = Font(bold=True, size=12)
            
            # Información de pago
            row += 2
            ws[f'A{row}'] = f'Método de Pago: Stripe'
            ws[f'A{row}'].font = Font(bold=True)
            row += 1
            ws[f'A{row}'] = f'Estado: {venta.estado.upper()}'
            
            # Ajustar ancho de columnas
            ws.column_dimensions['A'].width = 40
            ws.column_dimensions['B'].width = 12
            ws.column_dimensions['C'].width = 18
            ws.column_dimensions['D'].width = 18
            
            # Guardar en buffer
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            # Retornar archivo
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="factura_{comprobante.nro}.xlsx"'
            return response
            
        except Venta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Venta no encontrada'
            }, status=404)
        except Exception as e:
            logger.error(f"Error en ComprobanteExcelView.get: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)

