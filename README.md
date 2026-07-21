# heurist_to_tei
Transformation pipeline from Heurist database to TEI depot.
The Heurist file is reused from Heurist-analyzer repository [https://github.com/LostMa-ERC/Heurist-analyser/blob/main/pyproject.toml]

## Pour lancer la pipeline
Cloner le repository
```bash
git clone https://github.com/LostMa-ERC/heurist_to_tei
```
Se placer dans le dossier du repository
```bash
cd chemin/vers/dossier
```
Créer un environnement virtuel 
```bash
python3 -m venv env
```
Lancer l'environnement virtuel 
```bash
source env/bin/activate
```
Installer les dépendances 
```bash
pip install -r requirements.txt
```
Lancer le script en précisant les languages souhaités (code ISO + nom entier, ex : "dum (Middle Dutch)") 
```bash
python3 main.py --languages "STR" --output ./output/
```

