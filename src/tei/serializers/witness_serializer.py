# -*- coding: utf-8 -*-
"""
src/tei/serializers/witness.py

Sérialise chaque ligne du DataFrame witnesses produit par build_witnesses()
en un fichier TEI-P5 individuel conforme au schéma witness.rng.

Un fichier par witness, nommé hid_{H-ID}.xml, écrit dans output_dir.

Dépendances :
    - src/tei/models/witness.py  : modèles Pydantic
    - lxml                       : production du XML
"""

import logging
import re
from pathlib import Path

import pandas as pd
from lxml import etree

from src.tei.models.witness import (
    Witness, TitleStmt, LangUsage, Language, Lang,
    Creation, Date, MsDesc, MsIdentifier, Settlement,
    Repository, Idno, AltIdentifier, Location, Collection,
    MsFrag, PhysDesc, ObjectDesc, SupportDesc, Support,
    LayoutDesc, Layout, Dimensions, HandDesc, HandNote,
    DecoDesc, DecoNote, MsContents, MsItemStruct, Locus,
    Additional, Surrogates, Bibl,
)

log = logging.getLogger(__name__)

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS}


# ── Helpers XML ───────────────────────────────────────────────

def el(tag: str, text: str | None = None, **attrs) -> etree._Element:
    """Crée un élément TEI avec attributs et texte optionnels."""
    e = etree.Element(f"{{{TEI_NS}}}{tag}")
    for k, v in attrs.items():
        if v is not None:
            # Convertit xml_id → {xml_ns}id
            if k == "xml_id":
                e.set(f"{{{XML_NS}}}id", str(v))
            else:
                e.set(k.replace("_", ":"), str(v))
    if text is not None:
        e.text = str(text)
    return e


def sub(parent: etree._Element, tag: str, text: str | None = None, **attrs) -> etree._Element:
    """Crée un sous-élément TEI."""
    e = el(tag, text, **attrs)
    parent.append(e)
    return e


def val(row: pd.Series, col: str) -> str | None:
    """Retourne la valeur d'une colonne ou None si absente/NaN."""
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return str(v).strip() or None


# ── Parsing du code langue ────────────────────────────────────

def extract_lang_code(language_column: str) -> str | None:
    if not language_column:
        return None
    m = re.match(r"^(\w+)\s*\(", language_column.strip())
    return m.group(1).lower() if m else None


def extract_lang_label(language_column: str) -> str | None:
    if not language_column:
        return None
    m = re.search(r"\((.+)\)", language_column.strip())
    return m.group(1) if m else None


# ── Construction du modèle Pydantic depuis une ligne ─────────

def row_to_witness_model(row: pd.Series) -> Witness:
    """
    Construit un objet Pydantic Witness depuis une ligne du DataFrame.
    """
    hid = str(int(row["Witness_H-ID"]))

    # TitleStmt
    title_stmt = TitleStmt(title=val(row, "Witness_preferred_siglum") or f"Witness {hid}")

    # LangUsage
    lang_col = val(row, "Witness_regional_writing_style Name")
    language = Language(
        ident=extract_lang_code(lang_col) if lang_col else None,
        value=extract_lang_label(lang_col) if lang_col else None,
        langs=[
            Lang(n="regional", value=val(row, "Witness_regional_writing_style Name")),
            Lang(n="scripta",   value=val(row, "Witness_scripta_freetext")),
        ],
    )
    lang_usage = LangUsage(language=language)

    # Creation / Date
    date = Date(
        when=val(row, "Witness_date_of_creation"),
        certainty=val(row, "Witness_date_of_creation_certainty"),
        source=val(row, "Witness_date_of_creation_source"),
    )
    creation = Creation(date=date)

    # MsIdentifier
    settlement = Settlement(
        name=val(row, "Repository_city_preferred_name"),
        heurist_id=row.get("Repository_city_H-ID"),
    )
    repository = Repository(
        name=val(row, "Repository_preferred_name"),
        type="preferred_name",
        heurist_id=row.get("Repository_H-ID"),
        viaf=val(row, "Repository_VIAF"),
    )
    idno_heurist = Idno(value=hid, type="heurist")
    ms_identifier = MsIdentifier(
        settlement=settlement,
        repository=repository,
        idnos=[idno_heurist],
    )

    # MsDesc
    status = val(row, "Witness_status_witness") or "unknown"
    ms_desc = MsDesc(
        type=status.lower() if status.lower() in
            ["citation", "complete", "defective", "fragmentary", "lost", "unknown"]
            else "unknown",
        ms_identifier=ms_identifier,
        note=val(row, "Witness_status_notes"),
    )

    return Witness(
        xml_id=f"hid_{hid}",
        title_stmt=title_stmt,
        lang_usage=lang_usage,
        creation=creation,
        ms_desc=ms_desc,
    )


# ── Sérialisation du modèle Pydantic en XML TEI ───────────────

def witness_to_xml(witness: Witness) -> etree._Element:
    """
    Convertit un objet Witness en arbre XML TEI.
    """
    tei = el("TEI", xml_id=witness.xml_id)

    # ── teiHeader ─────────────────────────────────────────────
    header = sub(tei, "teiHeader")

    # fileDesc
    file_desc = sub(header, "fileDesc")
    title_stmt = sub(file_desc, "titleStmt")
    sub(title_stmt, "title", witness.title_stmt.title)

    source_desc = sub(file_desc, "sourceDesc")
    sub(source_desc, "p")

    # encodingDesc
    sub(header, "encodingDesc")

    # profileDesc
    profile_desc = sub(header, "profileDesc")

    # langUsage
    lang_usage_el = sub(profile_desc, "langUsage")
    lang = witness.lang_usage.language
    lang_el = sub(lang_usage_el, "language",
                  lang.value,
                  ident=lang.ident)
    for l in lang.langs:
        if l.value:
            sub(lang_el, "lang", l.value, n=l.n)

    # creation
    creation_el = sub(profile_desc, "creation")
    d = witness.creation.date
    date_attrs = {}
    if d.when:
        date_attrs["when"] = d.when
    if d.certainty:
        date_attrs["certainty"] = d.certainty
    if d.source:
        date_attrs["source"] = d.source
    sub(creation_el, "date", **date_attrs)

    # ── msDesc ────────────────────────────────────────────────
    ms = witness.ms_desc
    source_desc_header = sub(header, "sourceDesc")
    ms_desc_el = sub(source_desc_header, "msDesc", type=ms.type)

    ms_id = ms.ms_identifier
    ms_id_el = sub(ms_desc_el, "msIdentifier")
    if ms_id.settlement and ms_id.settlement.name:
        sub(ms_id_el, "settlement", ms_id.settlement.name)
    if ms_id.repository and ms_id.repository.name:
        sub(ms_id_el, "repository", ms_id.repository.name,
            type=ms_id.repository.type)
    for idno in ms_id.idnos:
        sub(ms_id_el, "idno", idno.value, type=idno.type)

    if ms.note:
        sub(ms_desc_el, "note", ms.note, type="witness-status")

    # ── text (corps vide) ─────────────────────────────────────
    text_el = sub(tei, "text")
    sub(text_el, "body")

    return tei


# ── Écriture sur disque ───────────────────────────────────────

def serialize_witnesses(witnesses_df: pd.DataFrame, output_dir: Path) -> None:
    """
    Sérialise chaque ligne du DataFrame en un fichier TEI XML.
    Produit un fichier hid_{H-ID}.xml par witness dans output_dir.

    Args:
        witnesses_df : DataFrame produit par build_witnesses()
        output_dir   : dossier de sortie (créé si absent)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(witnesses_df)
    success = 0

    for _, row in witnesses_df.iterrows():
        hid = row.get("Witness_H-ID")
        if pd.isna(hid):
            log.warning("  [!] Ligne sans H-ID ignorée.")
            continue

        try:
            model   = row_to_witness_model(row)
            xml_root = witness_to_xml(model)

            tree = etree.ElementTree(xml_root)
            etree.indent(tree, space="  ")

            output_path = output_dir / f"hid_{int(hid)}.xml"
            tree.write(
                output_path,
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=True,
            )
            success += 1
            log.info(f"  ✓ {output_path.name}")

        except Exception as e:
            log.error(f"  [!] Erreur pour witness H-ID {hid} : {e}")

    log.info(f"  {success}/{total} fichier(s) witness produit(s) dans {output_dir}")
