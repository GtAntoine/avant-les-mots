from fpdf import FPDF
from pathlib import Path
import re

class BookPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.add_font('DejaVu', '', 'C:/Windows/Fonts/arial.ttf')
        self.add_font('DejaVu', 'B', 'C:/Windows/Fonts/arialbd.ttf')
        self.add_font('DejaVu', 'I', 'C:/Windows/Fonts/ariali.ttf')
        self.add_font('DejaVu', 'BI', 'C:/Windows/Fonts/arialbi.ttf')

    def header(self):
        pass

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font('DejaVu', '', 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, str(self.page_no()), align='C')

    def chapter_title(self, title):
        self.add_page()
        self.set_font('DejaVu', 'B', 16)
        self.set_text_color(0, 0, 0)
        self.ln(30)
        clean_title = re.sub(r'^#+\s*', '', title)
        self.multi_cell(0, 10, clean_title, align='C')
        self.ln(15)

    def section_title(self, title):
        self.ln(10)
        self.set_font('DejaVu', 'B', 13)
        clean_title = re.sub(r'^#+\s*', '', title)
        self.multi_cell(0, 8, clean_title, align='C')
        self.ln(6)

    def subsection_title(self, title):
        self.ln(6)
        self.set_font('DejaVu', 'B', 11)
        clean_title = re.sub(r'^#+\s*', '', title)
        self.multi_cell(0, 7, clean_title)
        self.ln(4)

    def body_text(self, text, italic=False, bold=False):
        if bold and italic:
            self.set_font('DejaVu', 'BI', 10)
        elif bold:
            self.set_font('DejaVu', 'B', 10)
        elif italic:
            self.set_font('DejaVu', 'I', 10)
        else:
            self.set_font('DejaVu', '', 10)
        self.set_text_color(26, 26, 26)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def separator(self):
        self.ln(6)

    def blockquote(self, text):
        self.set_font('DejaVu', 'I', 9)
        self.set_text_color(68, 68, 68)
        self.set_x(20)
        self.multi_cell(0, 5, text)
        self.set_text_color(0, 0, 0)
        self.ln(2)

def parse_markdown(pdf, content):
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if line == '---':
            pdf.separator()
            i += 1
            continue

        if line.startswith('# '):
            pdf.chapter_title(line)
            i += 1
            continue

        if line.startswith('## '):
            pdf.section_title(line)
            i += 1
            continue

        if line.startswith('### '):
            pdf.subsection_title(line)
            i += 1
            continue

        if line.startswith('> '):
            text = line[2:]
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            pdf.blockquote(text)
            i += 1
            continue

        italic = False
        bold = False
        text = line

        if re.match(r'^\*[^*]+\*$', line):
            italic = True
            text = line.strip('*')
        elif re.match(r'^\*\*[^*]+\*\*$', line):
            bold = True
            text = line.strip('*')
        else:
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)

        pdf.body_text(text, italic=italic, bold=bold)
        i += 1

# Chemins
chapters_dir = Path("chapitres")
output_pdf = Path("Avant_les_mots.pdf")

# Chapitres (19 chapitres)
chapter_files = [f"chapitre_{i:02d}.md" for i in range(1, 20)]

# Créer le PDF
print("Création du PDF...")
pdf = BookPDF()
pdf.set_title("Avant les mots")
pdf.set_author("Anonyme")

# Page de titre
pdf.add_page()
pdf.set_font('DejaVu', 'B', 28)
pdf.ln(80)
pdf.cell(0, 15, 'AVANT LES MOTS', align='C')
pdf.ln(25)
pdf.set_font('DejaVu', 'I', 12)
pdf.cell(0, 10, 'Roman', align='C')

# Lire et ajouter chaque chapitre
for chapter_file in chapter_files:
    filepath = chapters_dir / chapter_file
    if filepath.exists():
        print(f"  - {chapter_file}")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            parse_markdown(pdf, content)
    else:
        print(f"  ! {chapter_file} non trouvé")

# Sauvegarder
pdf.output(str(output_pdf))
print(f"\nPDF créé : {output_pdf}")
