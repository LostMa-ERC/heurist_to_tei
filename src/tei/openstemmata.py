"""
src/tei/openstemmata.py
-----------------------
Récupère les fichiers TEI d'OpenStemmata depuis GitHub et en extrait
les éléments <listWit>, <textClass> et <text> pour les intégrer
au fichier TEI produit par la pipeline Heurist → TEI.

Source des données :
    DataFrame texts produit par build_texts() dans text_builder.py.
    Les colonnes utilisées sont :
        - "openstemmata id"  : nom du dossier GitHub
        - "language_COLUMN"  : code langue (ex. "dum (Middle Dutch)")
        - "preferred_name"   : nom du texte (pour le logging)

URL construite :
    https://raw.githubusercontent.com/OpenStemmata/database/main/
    data/{lang_code}/{openstemmata_id}/{openstemmata_id}.tei.xml

Relation N-N :
    Un texte peut avoir plusieurs stemmata associés. Le DataFrame
    texts est déjà explosé sur "in_stemma H-ID" par build_texts(),
    donc chaque ligne correspond à un couple (texte, stemma).
"""

import re
import logging
import requests
import pandas as pd
from pathlib import Path
from lxml import etree

log = logging.getLogger(__name__)

# URL de base du repo OpenStemmata
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/OpenStemmata/database/main/data"
)

# Namespace TEI
TEI_NS = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI_NS}


# ── Parsing du code langue ────────────────────────────────────

def extract_lang_code(language_column: str) -> str | None:
    """
    Extrait le code ISO depuis language_COLUMN.
    "dum (Middle Dutch)"  → "dum"
    "fro (Old French)"    → "fro"
    Retourne None si non parsable.
    """
    if not language_column:
        return None
    m = re.match(r"^(\w+)\s*\(", str(language_column).strip())
    return m.group(1).lower() if m else None


# ── Construction et récupération de l'URL ────────────────────

def build_tei_url(lang_code: str, openstemmata_id: str) -> str:
    """
    Construit l'URL raw GitHub du fichier TEI OpenStemmata.
    Ex : data/dum/Baker_2010_BestBeauvais/Baker_2010_BestBeauvais.tei.xml
    """
    return (
        f"{GITHUB_RAW_BASE}/{lang_code}/{openstemmata_id}"
        f"/{openstemmata_id}.tei.xml"
    )


def fetch_tei_xml(url: str) -> etree._Element | None:
    """
    Télécharge et parse le fichier TEI depuis l'URL GitHub.
    Retourne l'élément racine ou None en cas d'erreur.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        root = etree.fromstring(response.content)
        log.info(f"  ✓ Téléchargé : {url}")
        return root
    except requests.exceptions.HTTPError as e:
        log.warning(f"  [!] Fichier introuvable (HTTP {e.response.status_code}) : {url}")
        return None
    except requests.exceptions.RequestException as e:
        log.warning(f"  [!] Erreur réseau : {e}")
        return None
    except etree.XMLSyntaxError as e:
        log.warning(f"  [!] XML invalide : {e}")
        return None


# ── Extraction des éléments cibles ───────────────────────────

def extract_elements(root: etree._Element) -> dict:
    """
    Extrait <listWit>, <textClass> et <text> depuis le TEI OpenStemmata.
    Retourne un dict avec les éléments trouvés (None si absent).
    """
    return {
        "listWit":   root.find(".//tei:listWit",   NS),
        "textClass": root.find(".//tei:textClass", NS),
        "text":      root.find(".//tei:text",      NS),
    }


# ── Extraction des entrées depuis le DataFrame ────────────────

def load_openstemmata_ids_from_df(texts_df: pd.DataFrame) -> list[dict]:
    """
    Extrait les openstemmata_id et codes langue depuis le DataFrame texts.

    Le DataFrame est déjà explosé sur "in_stemma H-ID" par build_texts(),
    donc chaque ligne avec un "openstemmata id" non nul correspond à un
    couple (texte, stemma) à traiter.

    Retourne une liste de dicts dédupliqués :
        {preferred_name, openstemmata_id, lang_code}
    """
    # Filtrer les lignes avec un openstemmata id valide
    df = texts_df[texts_df["openstemmata id"].notna()].copy()

    if df.empty:
        log.warning("  Aucune entrée OpenStemmata dans le DataFrame.")
        return []

    results = []
    # Dédupliquer sur openstemmata_id : un même stemma peut apparaître
    # sur plusieurs lignes si plusieurs textes y sont liés
    seen = set()
    for _, row in df.iterrows():
        openstemmata_id = row["openstemmata id"]
        if openstemmata_id in seen:
            continue
        seen.add(openstemmata_id)

        lang_code = extract_lang_code(row.get("language_COLUMN", ""))
        if not lang_code:
            log.warning(
                f"  [!] Code langue non extrait pour "
                f"'{row.get('preferred_name', '?')}' "
                f"(openstemmata id : {openstemmata_id})"
            )
            continue

        results.append({
            "preferred_name":  row.get("preferred_name", ""),
            "openstemmata_id": openstemmata_id,
            "lang_code":       lang_code,
        })

    log.info(f"  {len(results)} entrée(s) OpenStemmata unique(s) trouvée(s).")
    return results


# ── Intégration dans le TEI cible ────────────────────────────

def integrate_into_tei(
    target_tei: etree._Element,
    elements: dict,
    openstemmata_id: str,
) -> None:
    """
    Intègre les éléments extraits dans le fichier TEI cible.

    - <listWit>   → inséré dans <sourceDesc>
    - <textClass> → inséré dans <profileDesc>
    - <text>      → inséré comme enfant de <TEI> avec @source
    """
    if elements["listWit"] is not None:
        source_desc = target_tei.find(".//tei:sourceDesc", NS)
        if source_desc is not None:
            source_desc.append(elements["listWit"])
            log.info("    → <listWit> intégré dans <sourceDesc>")
        else:
            log.warning("    [!] <sourceDesc> absent du TEI cible, <listWit> ignoré")

    if elements["textClass"] is not None:
        profile_desc = target_tei.find(".//tei:profileDesc", NS)
        if profile_desc is not None:
            profile_desc.append(elements["textClass"])
            log.info("    → <textClass> intégré dans <profileDesc>")
        else:
            log.warning("    [!] <profileDesc> absent du TEI cible, <textClass> ignoré")

    if elements["text"] is not None:
        elements["text"].set("source", openstemmata_id)
        target_tei.append(elements["text"])
        log.info(f"    → <text> intégré avec @source='{openstemmata_id}'")


# ── Fonction principale ───────────────────────────────────────

def fetch_and_integrate_from_df(
    texts_df: pd.DataFrame,
    target_tei_path: Path,
    output_path: Path,
) -> None:
    """
    Orchestre la récupération OpenStemmata et l'intégration dans le TEI cible
    à partir du DataFrame texts produit par build_texts().

    Args:
        texts_df        : DataFrame produit par build_texts()
        target_tei_path : fichier TEI produit par la pipeline Heurist → TEI
        output_path     : fichier TEI de sortie enrichi (enriched.xml)
    """
    log.info("── OpenStemmata : récupération et intégration ───────────")

    # 1. Charger le TEI cible
    target_tree = etree.parse(target_tei_path)
    target_root = target_tree.getroot()

    # 2. Extraire les entrées depuis le DataFrame
    entries = load_openstemmata_ids_from_df(texts_df)
    if not entries:
        log.warning("  Aucune entrée à traiter. Fichier TEI inchangé.")
        return

    # 3. Pour chaque entrée : télécharger, extraire, intégrer
    for entry in entries:
        openstemmata_id = entry["openstemmata_id"]
        lang_code       = entry["lang_code"]
        preferred_name  = entry["preferred_name"]

        log.info(f"  Traitement : {preferred_name} → {openstemmata_id} ({lang_code})")

        url  = build_tei_url(lang_code, openstemmata_id)
        root = fetch_tei_xml(url)

        if root is None:
            log.warning(f"  [!] Échec du téléchargement, ignoré : {openstemmata_id}")
            continue

        elements = extract_elements(root)
        integrate_into_tei(target_root, elements, openstemmata_id)

    # 4. Écrire le TEI enrichi
    tree_out = etree.ElementTree(target_root)
    etree.indent(tree_out, space="  ")
    tree_out.write(
        output_path,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    log.info(f"  Fichier TEI enrichi : {output_path}")