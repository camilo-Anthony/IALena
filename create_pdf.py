from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Informe de Eventos: Nepal (26 de Agosto de 2026)", ln=True, align='C')
pdf.ln(10)
pdf.multi_cell(0, 10, txt="Nota: La fecha solicitada (26 de agosto de 2026) corresponde a una fecha futura. No existen registros de eventos históricos para este día.")
pdf.output("C:\\Users\\hp\\Documents\\PROYECTOS\\JARVIS\\Resumen_Nepal_26_Agosto_2026.pdf")
