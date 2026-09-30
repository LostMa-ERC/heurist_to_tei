# -*- coding: utf-8 -*-
"""
src/tei/serializers/witness.py

Sérialise chaque ligne du DataFrame witnesses produit par build_witnesses()
en un fichier TEI-P5 individuel conforme au schéma witness.rng.

Un fichier par witness, nommé hid_{H-ID}.xml, sort dans le directory demandé.

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


# Helpers : Fonctions pour définir les éléments XML 

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
    sub(resp_stmt_1, "resp", "Project leader")
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

    funder = sub(title_stmt_el, "funder")
    sub(funder, "orgName", "European Research Council")
    note_1 = sub(funder, "note")
    note_1.text = "Horizon Europe ERC Grant number "
    sub(note_1, "idno", "101117408")
    sub(
        funder,
        "note",
        "Funded by the European Research Council. Views and opinions expressed are "
        "however those of the author(s) only and not necessarily reflect those of "
        "the European Union or the European Research Council. Neither the European "
        "Union nor the granting authority can be held responsible for them.",
    )

# Parsing pour récupérer le code ISO de la langue

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


def parse_locus_range(page_ranges) -> tuple[str | None, str | None]:
   
    if page_ranges is None:
        return None, None
    if isinstance(page_ranges, (list, tuple)):
        if len(page_ranges) == 0:
            return None, None
        page_ranges = page_ranges[0]
    if isinstance(page_ranges, float) and pd.isna(page_ranges):
        return None, None

    # Nettoie la représentation texte d'une liste : ['30r-50v'] = 30r-50v
    s = str(page_ranges).strip().strip("[]").strip().strip("'\"").strip()

    if not s or "-" not in s or s.startswith("?"):
        return None, None
    start, end = s.split("-", 1)
    return start.strip() or None, end.strip() or None

def viaf_uri(viaf: str | None) -> str | None:
    """Convertit la valeur VIAF en URI ou None."""
    if not viaf:
        return None
    try:
        f = float(viaf)
    except ValueError:
        return None
    if f > 2**53:   # précision perdue en float : valeur inexploitable
        return None
    return f"https://viaf.org/viaf/{int(f)}"


def add_frag_ms_identifier(frag_el: etree._Element, ms_id: MsIdentifier | None) -> None:
    """msIdentifier d'un msFrag : structure toujours complète, avec ou sans données."""
    ms_id_el = sub(frag_el, "msIdentifier")

    settlement = ms_id.settlement.name if ms_id and ms_id.settlement else None
    sub(ms_id_el, "settlement", settlement)

    repo = ms_id.repository if ms_id else None
    sub(ms_id_el, "repository",
        repo.name if repo else None,
        ref=viaf_uri(repo.viaf) if repo else None)

    shelfmark = next(
        (i.value for i in ms_id.idnos if i.type == "shelfmark"), None
    ) if ms_id else None
    sub(ms_id_el, "idno", shelfmark, type="shelfmark")

    alt_el = sub(ms_id_el, "altIdentifier", type="old-shelfmark")
    old = ms_id.alt_identifier.idno.value if ms_id and ms_id.alt_identifier else None
    sub(alt_el, "idno", old)

# Construction du modèle Pydantic depuis une ligne

def rows_to_witness_model(group_rows: pd.DataFrame) -> Witness:
    """
    Construit un objet Pydantic Witness
    Une ligne = une Part du même Witness
    """
    group_rows = (
        group_rows
        .drop_duplicates(subset="Part_H-ID")   # l'explode/merge peut dupliquer des lignes
        .sort_values("Part_div_order",
                     key=lambda s: pd.to_numeric(s, errors="coerce"),
                     na_position="last")       # msFrag dans l'ordre des parts
    )
    
    first_row = group_rows.iloc[0]  # Métadonnées du Witness (identiques pour tout le groupe)
    hid = str(int(first_row["Witness_H-ID"]))


    # TitleStmt
    title_stmt = TitleStmt(
        witness_siglum=val(first_row, "Witness_preferred_siglum") or f"Witness {hid}",
        text_name=val(first_row, "TextTable_preferred_name"),
    )

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

    # Boucle pour construire un msFrag par Part
    
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
            viaf=val(row, "Repository_VIAF"),
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

        # Valeur brute (liste) : parse_locus_range la gère
        locus_from, locus_to = parse_locus_range(row.get("Part_page_ranges"))
        frag_ms_contents = MsContents(ms_item_structs=[
            MsItemStruct(locus=Locus(from_=locus_from, to=locus_to or ""))
        ])

        additional = None
        digitization_uri = val(row, "Digitization_URI")
        if digitization_uri:
            bibl = Bibl(
                type="digitisation",
                idno=Idno(value="", type="IIIF"),
                iiif_target=None,
                uri_text=digitization_uri,
            )
            additional = Additional(surrogates=Surrogates(bibl_list=[bibl]))

        ms_frags.append(MsFrag(
            ms_identifier=frag_ms_identifier,
            ms_contents=frag_ms_contents,
            additional=additional,
        ))

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
   


# Conversion objet python Witness vers arborescence TEI

def witness_to_xml(witness: Witness) -> etree._Element:
    """
    Convertit un objet Witness en arbre XML TEI.
    """
    tei = el("TEI", xml_id=witness.xml_id, nsmap=NSMAP)

    # ajout parce qu'il avait été déclaré trop loin 

    ms = witness.ms_desc

    # teiHeader
    header = sub(tei, "teiHeader")

    # fileDesc
    file_desc = sub(header, "fileDesc")
    title_stmt = sub(file_desc, "titleStmt")
    if witness.title_stmt.text_name:
        sub(title_stmt, "title", witness.title_stmt.text_name, type="text_name")
    sub(title_stmt, "title", witness.title_stmt.witness_siglum, type="witness_siglum")
    add_project_metadata(title_stmt)

    pub_stmt = sub(file_desc, "publicationStmt")
    sub(pub_stmt, "publisher", "ERC LostMA")
    sub(pub_stmt, "date", when="2026")
    availability = sub(pub_stmt, "availability")
    sub(
        availability,
        "licence",
        "CC BY 4.0",
        target="http://creativecommons.org/licenses/by/4.0/deed.en",
    )
    sub(availability, "p", "Les données sont disponibles sous licence CC BY 4.0.")

    source_desc_el = sub(file_desc, "sourceDesc")
    ms_desc_el = sub(source_desc_el, "msDesc", type=ms.type)

    # encodingDesc - commenté pour le moment mais à conserver pour le futur quand les HTR auront été intégrés
    # sub(header, "encodingDesc")

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

    # msDesc

    ms_id = ms.ms_identifier
    ms_id_el = sub(ms_desc_el, "msIdentifier")
    if ms_id.settlement and ms_id.settlement.name:
        sub(ms_id_el, "settlement", ms_id.settlement.name)
    if ms_id.repository and ms_id.repository.name:
        sub(ms_id_el, "repository", ms_id.repository.name,
            type=ms_id.repository.type)
    for idno in ms_id.idnos:
        sub(ms_id_el, "idno", idno.value, type=idno.type)

  
    # msFrag : au moins un, même sans données Heurist
    for frag in (ms.ms_frags or [None]):
        frag_el = sub(ms_desc_el, "msFrag")
        add_frag_ms_identifier(frag_el, frag.ms_identifier if frag else None)

        if frag and frag.ms_contents and frag.ms_contents.ms_item_structs:
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

        if (frag and frag.additional and frag.additional.surrogates
                and frag.additional.surrogates.bibl_list):
            additional_el = sub(frag_el, "additional")
            surrogates_el = sub(additional_el, "surrogates")
            for bibl in frag.additional.surrogates.bibl_list:
                bibl_el = sub(surrogates_el, "bibl", type=bibl.type)
                # l'URI de Digitization_URI devient @target de <ptr>, sans texte dans <bibl>
                sub(bibl_el, "ptr", target=bibl.iiif_target or bibl.uri_text)

    if ms.note:
        sub(ms_desc_el, "note", ms.note, type="witness-status")

    # text - à reprendre quand j'aurai branché les sorties HTR - pour le moment c'est juste un p 
    # pour que les fichiers valident. 
    text_el = sub(tei, "text")
    body_el = sub(text_el, "body")
    sub(body_el, "p")   # <p/> vide : permet de valider en l'absence de transcription

    return tei


# Sérialisation du témoin : 

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
            model = rows_to_witness_model(group_rows)  
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

    
