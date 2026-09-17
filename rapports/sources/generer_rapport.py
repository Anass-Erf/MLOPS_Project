"""Générateur documentaire autonome ; ne modifie aucun fichier applicatif."""
from pathlib import Path
import json,re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'rapports'
NAME='Rapport_Academique_MLOps_DataOps_Stress_Hydrique_Final'
doc=Document()
sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(2.3);sec.bottom_margin=Cm(2.3)
sec.left_margin=Cm(2.5);sec.right_margin=Cm(2.5)
sec.header_distance=Cm(.9);sec.footer_distance=Cm(1)
styles=doc.styles
for name in ['Normal','Body Text']:
 s=styles[name];s.font.name='Times New Roman';s.font.size=Pt(11)
 s.paragraph_format.line_spacing=1.15;s.paragraph_format.space_after=Pt(5)
 s.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
for i,size in [(1,17),(2,13),(3,11.5)]:
 s=styles[f'Heading {i}'];s.font.name='Times New Roman';s.font.size=Pt(size)
 s.font.bold=True;s.font.color.rgb=RGBColor.from_string('183E50')
 s.paragraph_format.space_before=Pt(10);s.paragraph_format.space_after=Pt(7)
 s.paragraph_format.keep_with_next=True
for name in ['Caption']:
 styles[name].font.name='Times New Roman';styles[name].font.size=Pt(9.5)
 styles[name].paragraph_format.space_after=Pt(4)
 styles[name].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
for name,size in [('Source',8),('Code',8),('FrontTitle',18)]:
 if name not in styles:
  styles.add_style(name,1)
 s=styles[name];s.font.name='Consolas' if name=='Code' else 'Times New Roman';s.font.size=Pt(size)
 s.paragraph_format.space_after=Pt(4);s.paragraph_format.line_spacing=1.0
 if name=='Source':s.font.color.rgb=RGBColor.from_string('536670')
 if name=='Code':s.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
 if name=='FrontTitle':s.font.bold=True;s.font.color.rgb=RGBColor.from_string('183E50')
lang=OxmlElement('w:lang');lang.set(qn('w:val'),'fr-FR');styles['Normal']._element.get_or_add_rPr().append(lang)
settings=doc.settings.element
upd=OxmlElement('w:updateFields');upd.set(qn('w:val'),'true');settings.append(upd)
core=doc.core_properties;core.title='Prédiction du stress hydrique des cultures — DataOps/MLOps';core.author='Équipe de projet — Master Intelligence Artificielle';core.subject='Rapport académique fondé sur le dépôt 0f3bc50';core.language='fr-FR'
figures=[];tables=[]
pending_break=False
for idx in [1,2,3]:
 name=f'TOC {idx}'
 if name not in styles:styles.add_style(name,1)
 styles[name].font.name='Times New Roman';styles[name].font.size=Pt(10)
 styles[name].paragraph_format.space_after=Pt(1)
 styles[name].paragraph_format.line_spacing=1.0

def field(p,instruction,placeholder=''):
 r=p.add_run();b=OxmlElement('w:fldChar');b.set(qn('w:fldCharType'),'begin');r._r.append(b)
 r=p.add_run();t=OxmlElement('w:instrText');t.set(qn('xml:space'),'preserve');t.text=' '+instruction+' ';r._r.append(t)
 r=p.add_run();s=OxmlElement('w:fldChar');s.set(qn('w:fldCharType'),'separate');r._r.append(s)
 p.add_run(placeholder)
 r=p.add_run();e=OxmlElement('w:fldChar');e.set(qn('w:fldCharType'),'end');r._r.append(e)

def page():
 global pending_break
 pending_break=True
def apply_break(para):
 global pending_break
 if pending_break:
  para.paragraph_format.page_break_before=True;pending_break=False
 return para
def p(text,style=None):return apply_break(doc.add_paragraph(text,style))
def heading(text,level=1):return apply_break(doc.add_heading(text,level))
def front(text):return p(text,'FrontTitle')
def source(text):p('Source : '+text,'Source')
def code(text):
 for line in text.splitlines():
  para=p(line,'Code')
  para.paragraph_format.keep_with_next=False

def footer(section,fmt,start):
 section.footer.is_linked_to_previous=False
 para=section.footer.paragraphs[0];para.alignment=WD_ALIGN_PARAGRAPH.CENTER
 field(para,'PAGE','1')
 for r in para.runs:r.font.name='Times New Roman';r.font.size=Pt(9)
 n=OxmlElement('w:pgNumType');n.set(qn('w:fmt'),fmt);n.set(qn('w:start'),str(start));section._sectPr.append(n)

def caption(label,number,text):
 para=p('','Caption');para.paragraph_format.keep_with_next=(label=='Tableau')
 para.add_run(label+' ');field(para,f'SEQ {label} \\* ARABIC',str(number));para.add_run(' — '+text)

def table(title,rows):
 tables.append(title);caption('Tableau',len(tables),title)
 t=doc.add_table(rows=1, cols=len(rows[0]));t.autofit=False;t.style='Table Grid'
 n=len(rows[0]);widths={2:[5.2,10.8],3:[3.8,6.4,5.8],4:[3.3,4.3,4.2,4.2],5:[2.6,5.4,2,2.5,3.5]}.get(n,[16/n]*n)
 if rows[0][0]=='ID':widths=[1.1,9.4,1.6,1.4,2.5]
 if 'Modèle'==rows[0][0] and n==5:widths=[4.2,2.5,2.5,2.5,4.3]
 if rows[0][0]=='Ensemble':widths=[2.5,4,3.4,3.4,2.7]
 if rows[0][0]=='Site' and n==5:widths=[3,2.3,2.3,4.2,4.2]
 for col,w in zip(t.columns,widths):col.width=Cm(w)
 for idx,row in enumerate(rows):
  cells=t.rows[0].cells if idx==0 else t.add_row().cells
  for cell,text,w in zip(cells,row,widths):
   cell.width=Cm(w)
   text=text.strip()
   # Permet le retour des très longues empreintes sans modifier leur contenu visible.
   text=re.sub(r'([a-f0-9]{32})(?=[a-f0-9]{32})',r'\1\u200b',text) if False else text
   cell.text=text
   for par in cell.paragraphs:
    par.paragraph_format.space_after=Pt(3);par.paragraph_format.space_before=Pt(3);par.paragraph_format.line_spacing=1.0
    par.alignment=WD_ALIGN_PARAGRAPH.LEFT
    for r in par.runs:r.font.name='Times New Roman';r.font.size=Pt(9)
   tcpr=cell._tc.get_or_add_tcPr()
   sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'DFEBF0' if idx==0 else ('F5F8FA' if idx%2==0 else 'FFFFFF'));tcpr.append(sh)
   if idx==0:
    for r in cell.paragraphs[0].runs:r.bold=True
  trpr=t.rows[-1]._tr.get_or_add_trPr();nosplit=OxmlElement('w:cantSplit');trpr.append(nosplit)
  if idx==0:
   repeat=OxmlElement('w:tblHeader');trpr.append(repeat)

def figure(path,title,src,maxheight):
 figures.append(title);n=len(figures)
 # Renvoi dans le texte distinct de la légende.
 para=p(f'Cette étape est illustrée à la figure {n}.','Source')
 para.paragraph_format.space_after=Pt(2);para.paragraph_format.keep_with_next=True
 im=Image.open(ROOT/path);ratio=im.width/im.height
 width=min(16,float(maxheight)*0.87*ratio)
 para=p('');para.alignment=WD_ALIGN_PARAGRAPH.CENTER;para.paragraph_format.keep_with_next=True
 para.add_run().add_picture(str(ROOT/path),width=Cm(width))
 caption('Figure',n,title);source(src)

# Page de garde, noms modifiables et emplacement de logo volontairement neutre.
for text,size in [('Université Hassan II de Casablanca',18),("Faculté des Sciences Ben M’Sik",15),("Master d’Intelligence Artificielle",14),('Module MLOps & DataOps',13)]:
 para=p(text);para.alignment=WD_ALIGN_PARAGRAPH.CENTER
 for r in para.runs:r.font.size=Pt(size);r.bold=True
p('')
para=p('[ Emplacement du logo de l’université / de la faculté ]');para.alignment=WD_ALIGN_PARAGRAPH.CENTER
para.runs[0].font.size=Pt(10);para.runs[0].font.color.rgb=RGBColor.from_string('667680')
p('')
para=p('Prédiction du stress hydrique\ndes cultures');para.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in para.runs:r.font.size=Pt(24);r.bold=True;r.font.color.rgb=RGBColor.from_string('183E50')
para=p('Conception et mise en œuvre\nd’un pipeline DataOps/MLOps');para.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in para.runs:r.font.size=Pt(17)
p('')
p('Réalisé par :')
for i in range(1,8):
 para=p(f'Étudiant {i} : [Nom et prénom]');para.paragraph_format.space_after=Pt(3)
p('')
p('Encadré par : Pr. Mohammed AIT DAOUD')
para=p('Année universitaire : 2025–2026');para.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in para.runs:r.bold=True

s=doc.add_section(WD_SECTION.NEW_PAGE);footer(s,'lowerRoman',1)
front('Remerciements')
p('Nous adressons nos remerciements à Pr. Mohammed AIT DAOUD pour le cadre pédagogique du module MLOps & DataOps. Nous remercions également la Faculté des Sciences Ben M’Sik et le Master d’Intelligence Artificielle de l’Université Hassan II de Casablanca. Ce travail mobilise des données et outils ouverts dont la documentation a rendu possible une démarche reproductible. Les choix scientifiques, les interprétations et les limites présentés dans ce rapport restent sous la responsabilité de l’équipe.')
front('Résumé')
p('Ce rapport présente la conception et l’implémentation d’un système DataOps/MLOps de prédiction du stress hydrique modélisé du blé sur trois sites marocains : Meknès, Settat et Marrakech. Les séries quotidiennes NASA POWER couvrent janvier 2015 à juin 2024, soit 10 407 observations. Un bilan hydrique à paramètres de sol hypothétiques fournit la cible du lendemain, comprise entre zéro et un. Le modèle utilise trente jours d’historique et vingt-cinq variables explicatives ; il n’est pas entraîné sur des mesures de stress au champ.')
p('Le chemin DataOps associe dlt, DuckDB, dbt, un contrat de données Python/SQL et Dagster. Il reproduit les sorties du pipeline initial tout en isolant ses dépendances et ses résultats. La chaîne MLOps comprend une validation chronologique, quatre modèles, le suivi MLflow, un registre candidat/production, FastAPI, une interface Streamlit, Docker Compose, une CI GitHub Actions et des rapports de monitoring.')
p('HistGradientBoosting est sélectionné par la validation. Sur 1 074 observations de test, la RMSE vaut 0,188591, la MAE 0,140200 et le R² 0,625080. Une persistance fondée sur l’état simulé complet obtient une erreur plus faible. Les résultats démontrent une chaîne reproductible et l’approximation d’un proxy ; ils ne valident pas des décisions d’irrigation. Le rapport distingue les preuves techniques, les limites scientifiques et la reconstruction pédagogique des phases Agile.')
p('Mots-clés : stress hydrique ; blé ; NASA POWER ; DataOps ; MLOps ; dlt ; DuckDB ; dbt ; Dagster ; MLflow ; validation chronologique.')
page();front('Abstract')
p('This report describes an end-to-end DataOps/MLOps system for next-day prediction of a modeled wheat water-stress index at three Moroccan sites: Meknes, Settat and Marrakech. NASA POWER daily weather covers January 2015 to June 2024, yielding 10,407 observations. A continuous water-balance model with assumed soil parameters produces bounded proxy labels. Predictions use thirty consecutive days of weather and twenty-five features; field-measured crop stress is not available.')
p('The additional DataOps pathway integrates dlt ingestion, DuckDB storage, dbt transformations, Python and SQL data contracts, and Dagster orchestration. It reproduces the original canonical weather and feature datasets. The MLOps workflow includes chronological model selection, MLflow tracking and registry, FastAPI serving, a Streamlit client, Docker Compose, GitHub Actions and monitoring reports. Histogram gradient boosting achieves a test RMSE of 0.188591 and R² of 0.625080, while a persistence comparator using full simulated state performs better. The report therefore emphasizes reproducibility and transparent scientific limitations rather than claiming field-validated irrigation support.')
p('Keywords: crop water stress; wheat; weather data; DataOps; MLOps; data contract; model registry; chronological evaluation.')
front('Liste des abréviations')
t=doc.add_table(rows=0,cols=2);t.style='Table Grid'
for a,b in [('API','Interface de programmation applicative'),('CI / CD','Intégration continue / livraison ou déploiement continus'),('EDA','Analyse exploratoire des données'),('ET0 / ETc','Évapotranspiration de référence / de la culture'),('FC / WP','Capacité au champ / point de flétrissement'),('Ks / Kc','Coefficient de stress / coefficient cultural'),('LST','Temps solaire local'),('MAE / RMSE','Erreur absolue moyenne / racine de l’erreur quadratique moyenne'),('PSI / KS','Population Stability Index / Kolmogorov–Smirnov'),('PR','Pull Request'),('TAW / RAW','Eau totale disponible / eau facilement utilisable'),('SHA-256','Fonction d’empreinte cryptographique')]:
 c=t.add_row().cells;c[0].text=a;c[1].text=b
 for cell in c:
  for r in cell.paragraphs[0].runs:r.font.size=Pt(10)
page();front('Table des matières')
p('Table automatique. Dans Microsoft Word : Ctrl+A, puis F9 pour actualiser les champs après modification.','Source')
field(p(''),'TOC \\o "1-2" \\h \\z \\u','Table des matières — actualisation automatique à la génération.')
page();front('Liste des figures')
field(p(''),'TOC \\h \\z \\c "Figure"','Liste automatique des figures.')
page();front('Liste des tableaux')
field(p(''),'TOC \\h \\z \\c "Tableau"','Liste automatique des tableaux.')
s=doc.add_section(WD_SECTION.NEW_PAGE);footer(s,'decimal',1)
s.header.is_linked_to_previous=False
h=s.header.paragraphs[0];h.text='STRESS HYDRIQUE DES CULTURES  •  MLOps & DataOps';h.alignment=WD_ALIGN_PARAGRAPH.RIGHT
for r in h.runs:r.font.name='Times New Roman';r.font.size=Pt(8);r.font.color.rgb=RGBColor.from_string('657780')
lines=(OUT/'sources/rapport.md').read_text().splitlines();i=0
while i<len(lines):
 line=lines[i].strip();i+=1
 if not line:continue
 if line=='@page':page();continue
 if line.startswith('@source '):source(line[8:]);continue
 if line.startswith('@fig '):
  parts=[x.strip() for x in line[5:].split('|')];figure(*parts);continue
 if line.startswith('@table '):
  rows=[]
  while i<len(lines) and lines[i].strip()!='@end':
   rows.append([x.strip() for x in lines[i].split('|')]);i+=1
  i+=1;table(line[7:],rows);continue
 if line.startswith('```'):
  buf=[]
  while i<len(lines) and not lines[i].startswith('```'):buf.append(lines[i]);i+=1
  i+=1;code('\n'.join(buf));continue
 if line.startswith('#'):
  n=len(line)-len(line.lstrip('#'));heading(line[n:].strip(),n);continue
 p(line)
# Requête complète, répartie sur deux pages, valeurs directement lues du fichier réel.
req=json.loads((ROOT/'artifacts/example_request.json').read_text())
for half in range(2):
 page();heading('Annexe J — Requête JSON complète'+(' (suite)' if half else ''),2)
 p('Reproduction du fichier de référence ; concaténer les deux blocs sans leurs titres.','Source')
 if half==0:code('{\n  "site_id": '+json.dumps(req['site_id'])+',\n  "crop": "wheat",\n  "history": [')
 for idx,row in enumerate(req['history'][half*15:(half+1)*15],start=half*15):
  # Deux lignes par journée pour préserver la lisibilité, sans supprimer de champs.
  keys=list(row);a=keys[:4];b=keys[4:]
  first='    {'+', '.join(json.dumps(k)+': '+json.dumps(row[k]) for k in a)+','
  second='     '+', '.join(json.dumps(k)+': '+json.dumps(row[k]) for k in b)+'}'+(',' if idx<29 else '')
  code(first+'\n'+second)
 if half==1:code('  ]\n}')
# Footer cover blank, no automatic numbering on cover.
OUT.mkdir(exist_ok=True)
path=OUT/f'{NAME}.docx';doc.save(path)
(OUT/'sources/inventaire_illustrations.json').write_text(json.dumps({'figures':figures,'tableaux':tables},indent=2,ensure_ascii=False))
print(path)
print('Figures:',len(figures),'Tableaux:',len(tables),'Mots source:',len((OUT/'sources/rapport.md').read_text().split()))
