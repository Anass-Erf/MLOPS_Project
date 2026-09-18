from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path('rapports/sources');out.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11})
def draw(name,nodes,edges,size=(12,6)):
 fig,ax=plt.subplots(figsize=size);ax.set(xlim=(0,12),ylim=(0,6));ax.axis('off')
 for key,(x,y,w,h,label,color) in nodes.items():
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.06,rounding_size=0.10',facecolor=color,edgecolor='#294458',linewidth=1.2))
  ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=18,color='#152b3c',linespacing=1.35)
 for a,b,dashed in edges:
  x,y,w,h,*_=nodes[a];X,Y,W,H,*_=nodes[b]
  if abs(Y-y)<.6:
   start=(x+w,y+h/2) if X>x else (x,y+h/2);end=(X,Y+H/2) if X>x else (X+W,Y+H/2)
  else:
   start=(x+w/2,y if Y<y else y+h);end=(X+W/2,Y+H if Y<y else Y)
  ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=14,color='#486579',linewidth=1.3,linestyle='--' if dashed else '-',connectionstyle='arc3,rad=0.4' if name=='architecture' and a=='h' and b=='j' else 'arc3'))
 fig.tight_layout(pad=.5);fig.savefig(out/f'{name}.png',dpi=220,bbox_inches='tight');fig.savefig(out/f'{name}.svg',bbox_inches='tight');plt.close(fig)
blue='#e8f0f7';green='#e2f1ea';gold='#fff2d8'
draw('architecture',{
'a':(.15,4.6,2.5,.9,'NASA POWER\nJSON + manifestes',blue),'b':(3.2,4.6,2.5,.9,'dlt → DuckDB\nraw.raw_weather',blue),'c':(6.3,4.6,2.5,.9,'dbt staging\n→ ml_weather',blue),'d':(9.45,4.6,2.3,.9,'Contrat qualité\n+ CSV approuvé',green),
'e':(9.2,2.6,2.55,.9,'Features Python\n+ cible proxy',green),'f':(5.5,2.6,2.7,.9,'Entraînement explicite\nMLflow candidat',gold),'g':(1.1,2.6,3.25,.9,'Évaluation figée\npromotion séparée',gold),
'h':(1.1,.55,3.25,.9,'FastAPI\nmodèle de production',blue),'i':(5.5,.55,2.7,.9,'Client Streamlit',blue),'j':(9.2,.55,2.55,.9,'Événements\nMonitoring',blue)},[('a','b',False),('b','c',False),('c','d',False),('d','e',False),('e','f',False),('f','g',False),('g','h',True),('h','i',False),('h','j',True)])
# Separate execution and release boundaries are explained in caption/text.
draw('dagster',{
'a':(.3,4.65,3.2,.8,'nasa_snapshots\nsource externe',blue),'b':(4.3,4.65,3.2,.8,'ingest_weather',blue),'c':(8.3,4.65,3.2,.8,'dbt_transform',blue),
'd':(8.3,2.7,3.2,.8,'data_quality',green),'e':(4.3,2.7,3.2,.8,'build_features',green),'f':(4.3,.6,3.2,.8,'train_model',gold),'g':(8.3,.6,3.2,.8,'evaluate_model',gold)},[('a','b',False),('b','c',False),('c','d',False),('d','e',False),('e','f',True),('f','g',False)])
draw('lineage',{
'a':(.3,4.6,3.2,.9,'Instantanés immuables\nSHA-256 + requête',blue),'b':(4.4,4.6,3.2,.9,'Raw dlt\nprovenance par ligne',blue),'c':(8.5,4.6,3.2,.9,'stg_weather\ntypes et provenance',blue),
'd':(8.5,2.65,3.2,.9,'ml_weather\n13 colonnes canoniques',green),'e':(4.4,2.65,3.2,.9,'weather.csv\nempreinte approuvée',green),'f':(.3,2.65,3.2,.9,'features.csv\n25 variables + manifeste',green),
'g':(.3,.65,3.2,.9,'Modèle + métadonnées\nversion et empreinte',gold),'h':(4.4,.65,3.2,.9,'API / prédictions\nversion, site, date',gold),'i':(8.5,.65,3.2,.9,'Monitoring\nJSONL → rapports',gold)},[('a','b',False),('b','c',False),('c','d',False),('d','e',False),('e','f',False),('f','g',False),('g','h',True),('h','i',False)])
draw('deployment',{
'a':(.3,4.7,3.2,.85,'Navigateur\nport hôte 18501',blue),'b':(4.5,4.7,3.1,.85,'ui : 8501\nStreamlit',blue),'c':(8.6,4.7,3.1,.85,'api : 8000\nFastAPI',green),
'd':(8.6,2.5,3.1,.9,'Modèle embarqué\n+ volume api-events',green),'e':(4.5,2.5,3.1,.9,'weather-cache\ninstantanés UI',blue),'f':(.3,2.5,3.2,.9,'mlflow : 5000\nhôte 127.0.0.1:15000',gold),
'g':(.3,.4,3.2,.9,'mlflow-data\nSQLite + artefacts',gold),'h':(5.2,.4,5.4,.9,'Dagster local : 3000\nhors de Docker Compose', '#f0edf8')},[('a','b',False),('b','c',False),('c','d',False),('b','e',False),('f','g',False)])
