# heurist_to_tei
Transformation pipeline from Heurist database to TEI depot.
The Heurist file is reused from Heurist-analyzer repository [https://github.com/LostMa-ERC/Heurist-analyser/blob/main/pyproject.toml]

## Pour lancer la pipeline
Clone the repository
```bash
git clone https://github.com/LostMa-ERC/heurist_to_tei
```
Go to the directory
```bash
cd path/to/directory
```
Create the virtual environment  
```bash
python3 -m venv env
```
Start the virtual environment 
```bash
source env/bin/activate
```
Install the requirements 
```bash
pip install -r requirements.txt
```
Launch the script and specify which languages are required (ISO code + full name as listed on the [github.io](https://lostma-erc.github.io/), ex : "dum (Middle Dutch)")
```bash
python3 main.py --languages "STR" --output ./output/
```

