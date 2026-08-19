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
    Witness,
    TitleStmt,
    LangUsage,
    Language,
    Lang,
    Creation,
    Date,
    MsDesc,
    MsIdentifier,
    Settlement,
    Repository,
    Idno,
    AltIdentifier,
    Location,
    Collection,
    MsFrag,
    PhysDesc,
    ObjectDesc,
    SupportDesc,
    Support,
    LayoutDesc,
    Layout,
    Dimensions,
    HandDesc,
    HandNote,
    DecoDesc,
    DecoNote,
    MsContents,
    MsItemStruct,
    Locus,
    Additional,
    Surrogates,
    Bibl,
)

log = logging.getLogger(__name__)

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS}
NSMAP = {None: TEI_NS}


# ── Helpers XML ───────────────────────────────────────────────

def el(tag: str, text: str | None = None, nsmap=None, **attrs) -> etree._Element:
    """Crée un élément TEI avec attributs et texte optionnels."""
    e = etree.Element(f"{{{TEI_NS}}}{tag}", nsmap=nsmap)
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

def add_project_metadata(title_stmt_el: etree._Element) -> None:
    """
    Attention je n'ai ajouté que ceux qui ont vocation à apparaitre dans tous les corpus linguistiques. 
    Pour les contributeurs, il faudra rajouter une fonction par corpus : ex Cecile Vermaas pour le corpus DUM. 
    """
    # Principal
    principal = sub(title_stmt_el, "principal")
    person_name = sub(principal, "persName")
    sub(person_name, "forename", "Jean-Baptiste")
    sub(person_name, "surname", "Camps")

    resp_stmt_1 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_1, "resp", "Project's manager")
    person_name_1 = sub(resp_stmt_1, "persName", xml_id="JBC")
    sub(person_name_1, "forename", "Jean-Baptiste")
    sub(person_name_1, "surname", "Camps")

    resp_stmt_2 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_2, "resp", "Data architect")
    person_name_2 = sub(resp_stmt_2, "persName", xml_id="VR")
    sub(person_name_2, "forename", "Virgile")
    sub(person_name_2, "surname", "Reignier")

    resp_stmt_3 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_3, "resp", "Data architect")
    person_name_3 = sub(resp_stmt_3, "persName", xml_id="KC")
    sub(person_name_3, "forename", "Kelly")
    sub(person_name_3, "surname", "Christensen")

    resp_stmt_4 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_4, "resp", "Data architect")
    person_name_4 = sub(resp_stmt_4, "persName", xml_id="MM")
    sub(person_name_4, "forename", "Maud")
    sub(person_name_4, "surname", "Mélinand")

    resp_stmt_5 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_5, "resp", "HTR engineer")
    person_name_5 = sub(resp_stmt_5, "persName", xml_id="TM")
    sub(person_name_5, "forename", "Théo")
    sub(person_name_5, "surname", "Moins")

    resp_stmt_6 = sub(title_stmt_el, "respStmt")
    sub(resp_stmt_6, "resp", "HTR engineer")
    person_name_6 = sub(resp_stmt_6, "persName", xml_id="BH")
    sub(person_name_6, "forename", "Brenna")
    sub(person_name_6, "surname", "Hensley")


# ── Parsing du code langue ────────────────────────────────────

def extract_lang_code(language_column: str) -> str | None:
    if not language_column:
        return None
    m = re.search(r"([\w-]+)\s*\(", language_column.strip())
    return m.group(1).lower() if m else None


def extract_lang_label(s: str) -> str | None:
    if not s:
        return None
    m = re.search(r"\((.+)\)", s.strip())
    return m.group(1) if m else None

def cert_mapping(certainty: str | None) -> str | None:
    if not certainty:
        return None
    mapping = {
        "1. Very likely (> 90%)": "high",
        "2. Probable (33%-66%)":  "medium",
        "3. Unlikely (< 33%)":    "low",
        "4. Unknown":             "unknown",
        # Format court (cohérence avec text.py)
        "Very likely": "high",
        "Probable":    "medium",
        "Unlikely":    "low",
        "Unknown":     "unknown",
    }
    return mapping.get(certainty)

def parse_date_range(date_val) -> tuple[str | None, str | None]:
    """
    "1201-1300" → ("1201", "1300")
    "1200"      → ("1200", None)
    Texte libre → (None, None)
    """
    if not date_val:
        return None, None
    m = re.match(r"^(\d{3,4})\s*[-–]\s*(\d{3,4})$", str(date_val).strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^(\d{3,4})$", str(date_val).strip())
    if m:
        return m.group(1), None
    return None, None

def parse_locus_range(page_ranges: str | None) -> tuple[str | None, str | None]:
    """
    "12-23" → ("12", "23")
    "12"    → ("12", "12")
    Texte libre → (None, None)
    """
    if not page_ranges:
        return None, None
    m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", page_ranges.strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^(\d+)$", page_ranges.strip())
    if m:
        return m.group(1), m.group(1)
    return None, None

# ── Construction du modèle Pydantic depuis une ligne ─────────

def rows_to_witness_model(group_rows: pd.DataFrame) -> Witness:
    """
    Construit un objet Pydantic Witness depuis UN GROUP de lignes (Parts).
    Une ligne = une Part du même Witness.
    """
    first_row = group_rows.iloc[0]  # Métadonnées du Witness (identiques pour tout le groupe)
    hid = str(int(first_row["Witness_H-ID"]))

    # TitleStmt
    title_stmt = TitleStmt(title=val(first_row, "Witness_preferred_siglum") or f"Witness {hid}")

    # LangUsage
    lang_col = val(first_row, "Witness_regional_writing_style Name")
    language = Language(
        ident=extract_lang_code(lang_col),
        value=extract_lang_label(lang_col) if lang_col else None,
        langs=[
            Lang(n="regional", value=lang_col),
            Lang(n="scripta",  value=val(first_row, "Witness_scripta_freetext")),
        ],
    )
    lang_usage = LangUsage(language=language)

    # Creation / Date
    date_raw = val(first_row, "Witness_date_of_creation")
    not_before, not_after = parse_date_range(date_raw)
    date = Date(
        not_before=not_before,
        not_after=not_after,
        cert=cert_mapping(val(first_row, "Witness_date_of_creation_certainty")),
        source=val(first_row, "Witness_date_of_creation_source"),
        value=date_raw,
    )
    creation = Creation(date=date)

    # MsIdentifier (niveau msDesc) : uniquement l'idno heurist
    idno_heurist = Idno(value=hid, type="heurist")
    ms_identifier_top = MsIdentifier(idnos=[idno_heurist])

    # ── Construire UN msFrag par Part (par ligne du groupe) ────
    ms_frags = []
    for _, row in group_rows.iterrows():
        settlement = Settlement(
            name=val(row, "Repository_city Name"),
            heurist_id=val(row, "Repository_city H-ID"),
        )
        repository = Repository(
            name=val(row, "Repository_preferred_name"),
            type="preferred_name",
            heurist_id=val(row, "Repository_H-ID"),
        )

        idnos_frag = []
        shelfmark = val(row, "DocumentTable_current_shelfmark")
        if shelfmark:
            idnos_frag.append(Idno(value=shelfmark, type="shelfmark"))

        alt_identifier = None
        old_shelfmark = val(row, "DocumentTable_old_shelfmark")
        if old_shelfmark:
            alt_identifier = AltIdentifier(
                type="old-shelfmark",
                idno=Idno(value=old_shelfmark, type="old-shelfmark"),
            )

        frag_ms_identifier = MsIdentifier(
            settlement=settlement,
            repository=repository,
            idnos=idnos_frag,
            alt_identifier=alt_identifier,
        )

        # MsContents pour cette Part
        page_ranges = val(row, "Part_page_ranges")
        locus_from, locus_to = parse_locus_range(page_ranges)
        locus = Locus(from_=locus_from, to=locus_to or "")
        frag_ms_contents = MsContents(ms_item_structs=[MsItemStruct(locus=locus)])

        # Créer UN msFrag pour cette Part
        ms_frags.append(
            MsFrag(ms_identifier=frag_ms_identifier, ms_contents=frag_ms_contents)
        )

    # MsDesc
    status = val(first_row, "Witness_status_witness") or "unknown"
    ms_desc = MsDesc(
        type=status.lower() if status.lower() in
            ["citation", "complete", "defective", "fragmentary", "lost", "unknown"]
            else "unknown",
        ms_identifier=ms_identifier_top,
        note=val(first_row, "Witness_status_notes"),
        ms_frags=ms_frags,  # ← TOUS les msFrag
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
    tei = el("TEI", xml_id=witness.xml_id, nsmap=NSMAP)

    # ajout parce qu'il avait été déclaré trop loin 

    ms = witness.ms_desc

    # ── teiHeader ─────────────────────────────────────────────
    header = sub(tei, "teiHeader")

    # fileDesc
    file_desc = sub(header, "fileDesc")
    title_stmt = sub(file_desc, "titleStmt")
    sub(title_stmt, "title", witness.title_stmt.title)
    add_project_metadata(title_stmt)

    pub_stmt = sub(file_desc, "publicationStmt")
    sub(pub_stmt, "p", "Cette publication a été produite à partir des données du projet LostMa conservées sur Heurist.")

    source_desc_el = sub(file_desc, "sourceDesc")
    ms_desc_el = sub(source_desc_el, "msDesc", type=ms.type)

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
    if d.not_before:  date_attrs["notBefore"] = d.not_before
    if d.not_after:   date_attrs["notAfter"]  = d.not_after
    if d.cert:        date_attrs["cert"]      = d.cert
    if d.source:      date_attrs["source"]    = d.source
    sub(creation_el, "date", d.value, **date_attrs)

    # ── msDesc ────────────────────────────────────────────────

    ms_id = ms.ms_identifier
    ms_id_el = sub(ms_desc_el, "msIdentifier")
    if ms_id.settlement and ms_id.settlement.name:
        sub(ms_id_el, "settlement", ms_id.settlement.name)
    if ms_id.repository and ms_id.repository.name:
        sub(ms_id_el, "repository", ms_id.repository.name,
            type=ms_id.repository.type)
    for idno in ms_id.idnos:
        sub(ms_id_el, "idno", idno.value, type=idno.type)

    # ── msFrag (un par fragment physique) ──────────────────────
    for frag in ms.ms_frags:
        frag_el = sub(ms_desc_el, "msFrag")
        frag_id_el = sub(frag_el, "msIdentifier")
        fid = frag.ms_identifier

        if fid.settlement and fid.settlement.name:
            sub(frag_id_el, "settlement", fid.settlement.name)
        if fid.repository and fid.repository.name:
            sub(frag_id_el, "repository", fid.repository.name)
        for idno in fid.idnos:
            sub(frag_id_el, "idno", idno.value, type=idno.type)
        if fid.alt_identifier:
            alt_el = sub(frag_id_el, "altIdentifier", type=fid.alt_identifier.type)
            sub(alt_el, "idno", fid.alt_identifier.idno.value)

        if frag.ms_contents and frag.ms_contents.ms_item_structs:
            frag_contents_el = sub(frag_el, "msContents")
            for item in frag.ms_contents.ms_item_structs:
                item_el = sub(frag_contents_el, "msItemStruct")
                if item.locus:
                    attrs = {}
                    if item.locus.from_:
                        attrs["from"] = item.locus.from_
                    if item.locus.to:
                        attrs["to"] = item.locus.to
                    sub(item_el, "locus", **attrs)



    if ms.note:
        sub(ms_desc_el, "note", ms.note, type="witness-status")

    # ── text (corps vide) ─────────────────────────────────────
    text_el = sub(tei, "text")
    sub(text_el, "body")

    return tei


# ── Écriture sur disque ───────────────────────────────────────

def serialize_witnesses(witnesses_df: pd.DataFrame, output_dir: Path) -> None:
    """
    Sérialise chaque Witness (groupé par H-ID) en un fichier TEI XML.
    Un seul fichier hid_{H-ID}.xml par witness, contenant tous ses msFrag.

    Args:
        witnesses_df : DataFrame produit par build_witnesses() (avec Parts dupliquées)
        output_dir   : dossier de sortie
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Grouper par Witness_H-ID pour traiter toutes les Parts ensemble
    grouped = witnesses_df.groupby("Witness_H-ID")
    total_witnesses = len(grouped)
    success = 0

    for witness_hid, group_rows in grouped:
        try:
            # group_rows contient toutes les lignes (Parts) pour ce witness
            log.info(f"  Processing Witness {witness_hid} with {len(group_rows)} part(s)")
            
            # Utilise la première ligne pour les métadonnées de Witness
            first_row = group_rows.iloc[0]
            
            # Crée un Witness avec tous ses msFrag (un par Part)
            model = rows_to_witness_model(group_rows)  # ← NOUVELLE FONCTION
            xml_root = witness_to_xml(model)

            tree = etree.ElementTree(xml_root)
            etree.indent(tree, space="  ")

            output_path = output_dir / f"hid_{int(witness_hid)}.xml"
            tree.write(
                output_path,
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=True,
            )
            success += 1
            log.info(f"  ✓ {output_path.name}")

        except Exception as e:
            log.error(f"  [!] Erreur pour Witness H-ID {witness_hid} : {e}")
            import traceback
            traceback.print_exc()

    log.info(f"  {success}/{total_witnesses} fichier(s) witness produit(s) dans {output_dir}")

    
