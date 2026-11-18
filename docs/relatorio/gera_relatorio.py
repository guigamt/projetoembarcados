"""
Gera docs/Relatorio_Projeto_Final.docx a partir dos capitulos em Markdown desta pasta.
Precisa de:  pandoc  e  pip install python-docx
Uso:  python docs/relatorio/gera_relatorio.py
"""
import subprocess, glob, os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

D=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # pasta docs/
caps=sorted(glob.glob(D+'/relatorio/0*.md'))
tmp=os.path.join(D,'relatorio','_tmp.docx')
subprocess.run(['pandoc','-f','markdown','-t','docx','--resource-path',D+'/relatorio','-o',tmp]+caps,check=True)

doc=Document(tmp)
sec=doc.sections[0]
sec.page_width=Cm(21); sec.page_height=Cm(29.7)
sec.left_margin=Cm(2.5); sec.right_margin=Cm(2.0); sec.top_margin=Cm(2.5); sec.bottom_margin=Cm(2.0)

def fonte(st, nome='Arial', tam=None, negrito=None, cor=None):
    st.font.name=nome
    rpr=st.element.get_or_add_rPr(); rf=rpr.find(qn('w:rFonts'))
    if rf is None: rf=OxmlElement('w:rFonts'); rpr.append(rf)
    for a in ('w:ascii','w:hAnsi','w:cs','w:eastAsia'): rf.set(qn(a),nome)
    for a in ('w:asciiTheme','w:hAnsiTheme','w:cstheme','w:eastAsiaTheme'):
        if rf.get(qn(a)) is not None: del rf.attrib[qn(a)]
    if tam: st.font.size=Pt(tam)
    if negrito is not None: st.font.bold=negrito
    if cor: st.font.color.rgb=RGBColor(*cor)

nomes={s.name:s for s in doc.styles}
for n,t in (('Normal',11),('Body Text',11),('First Paragraph',11),('Compact',10)):
    if n in nomes: fonte(nomes[n],tam=t)
for n in ('Body Text','First Paragraph'):
    if n in nomes:
        pf=nomes[n].paragraph_format; pf.space_after=Pt(6); pf.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; pf.line_spacing=1.15
azul=(0x1F,0x3A,0x5F)
for n,t in (('Heading 1',16),('Heading 2',13),('Heading 3',11.5)):
    fonte(nomes[n],tam=t,negrito=True,cor=azul)
    nomes[n].paragraph_format.space_before=Pt(14 if n=='Heading 1' else 10); nomes[n].paragraph_format.space_after=Pt(6)
    nomes[n].paragraph_format.keep_with_next=True
nomes['Heading 1'].paragraph_format.page_break_before=True
for n in ('Source Code','Verbatim Char'):
    if n in nomes: fonte(nomes[n],nome='Consolas',tam=9)
for n,t,b in (('Capa',13,False),('CapaTitulo',24,True),('CapaSub',15,False)):
    if n in nomes:
        fonte(nomes[n],tam=t,negrito=b,cor=azul if n!='Capa' else None)
        nomes[n].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        nomes[n].paragraph_format.space_after=Pt(8)
if 'CapaTitulo' in nomes: nomes['CapaTitulo'].paragraph_format.space_before=Pt(120)
if 'CapaSub' in nomes: nomes['CapaSub'].paragraph_format.space_after=Pt(140)
for n in ('Image Caption','Table Caption','Caption','Captioned Figure'):
    if n in nomes:
        fonte(nomes[n],tam=9); nomes[n].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER

def borda(cell_tbl):
    tblPr=cell_tbl._tbl.tblPr
    b=OxmlElement('w:tblBorders')
    for lado in ('top','left','bottom','right','insideH','insideV'):
        e=OxmlElement('w:'+lado); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:space'),'0'); e.set(qn('w:color'),'8A96A3'); b.append(e)
    tblPr.append(b)
def sombra(cell,cor):
    tcPr=cell._tc.get_or_add_tcPr(); s=OxmlElement('w:shd'); s.set(qn('w:val'),'clear'); s.set(qn('w:color'),'auto'); s.set(qn('w:fill'),cor); tcPr.append(s)

for t in doc.tables:
    borda(t); t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for i,row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(2); p.paragraph_format.space_before=Pt(2)
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.size=Pt(9); r.font.name='Arial'
                    if i==0: r.font.bold=True
            if i==0: sombra(c,'DCE6F1')
        if i==0:
            trPr=row._tr.get_or_add_trPr(); h=OxmlElement('w:tblHeader'); trPr.append(h)
        trPr=row._tr.get_or_add_trPr(); cs=OxmlElement('w:cantSplit'); trPr.append(cs)

# realce dos campos a preencher
for p in list(doc.paragraphs)+[p for t in doc.tables for r in t.rows for c in r.cells for p in c.paragraphs]:
    for r in p.runs:
        if 'PREENCHER' in r.text:
            r.font.highlight_color=7  # amarelo
# figuras centralizadas
for p in doc.paragraphs:
    if p._p.findall('.//'+qn('w:drawing')):
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next=True
for sh in doc.inline_shapes:
    asp=sh.width/sh.height
    w=Cm(16) if asp>1.5 else (Cm(9.5) if asp>0.6 else Cm(5.5))
    sh.height=int(sh.height*w/sh.width); sh.width=w
# a capa e o resumo nao comecam com quebra antes da capa: primeiro Heading 1 (Resumo) quebra pagina, ok

# numero de pagina no rodape
fp=sec.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
run=fp.add_run()
for tipo,txt in (('begin',None),(None,'PAGE'),('end',None)):
    if tipo:
        e=OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'),tipo)
    else:
        e=OxmlElement('w:instrText'); e.set(qn('xml:space'),'preserve'); e.text=txt
    run._r.append(e)
run.font.size=Pt(9)
doc.core_properties.title='Projeto Final de Sistemas Embarcados - Central de alarme de 4 zonas'
doc.core_properties.author='Guilherme Meira; Lucas Freires'
saida=D+'/Relatorio_Projeto_Final.docx'
doc.save(saida)
os.remove(tmp)
# PDF: precisa do LibreOffice instalado (ou abrir o .docx no Word e salvar como PDF)
try:
    subprocess.run(['soffice','--headless','--convert-to','pdf','--outdir',D,saida],check=True)
except Exception as e:
    print('Nao gerei o PDF automaticamente:',e)
print('ok:',saida)
