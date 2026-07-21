# -*- coding: utf-8 -*-
"""
src/tei/serializers/text.py

Sérialise chaque groupe de lignes du DataFrame texts produit par build_texts()
en un fichier TEI-P5 individuel conforme au schéma text.rng.

Un fichier par text (groupé par H-ID), nommé hid_{H-ID}.xml, écrit dans output_dir.
La relation N-N avec Stemma est gérée par groupby sur H-ID avant sérialisation.

Dépendances :
    - src/tei/models/text.py  : modèles Pydantic
    - lxml                    : production du XML
"""

import logging
import re
from pathlib import Path

import pandas as pd
from lxml import etree

from src.tei.models.text import (
    Text, FileDesc, TitleStmt, Title, Author,
    SourceDesc, ListWit, Witness,
    EncodingDesc, ClassDecl, Taxonomy, Category,
    ProfileDesc, LangUsage, Language, Lang,
    Creation, Date, PlaceName,
    TextClass, Keywords, Term, CatRef,
    TextDesc, Constitution, Derivation,
    ParticDesc, ListPerson, Person,
    TextBody, Body, Graph, Node, Arc,
)

log = logging.getLogger(__name__)

TEI_NS  = "http://www.tei-c.org/ns/1.0"
XML_NS  = "http://www.w3.org/XML/1998/namespace"
NSMAP = {None: TEI_NS}

# ── Helpers XML ───────────────────────────────────────────────

def el(tag: str, text: str | None = None, nsmap=None, **attrs) -> etree._Element:
    e = etree.Element(f"{{{TEI_NS}}}{tag}", nsmap=nsmap)
    for k, v in attrs.items():
        if v is not None:
            if k == "xml_id":
                e.set(f"{{{XML_NS}}}id", str(v))
            else:
                e.set(k.replace("_", ":"), str(v))
    if text is not None:
        e.text = str(text)
    return e


def sub(parent: etree._Element, tag: str, text: str | None = None, **attrs) -> etree._Element:
    e = el(tag, text, **attrs)
    parent.append(e)
    return e


def val(row: pd.Series, col: str) -> str | None:
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return str(v).strip() or None


# ── Parsing ───────────────────────────────────────────────────

def extract_lang_code(s: str) -> str | None:
    if not s:
        return None
    m = re.match(r"^(\w+)\s*\(", s.strip())
    return m.group(1).lower() if m else None


def extract_lang_label(s: str) -> str | None:
    if not s:
        return None
    m = re.search(r"\((.+)\)", s.strip())
    return m.group(1) if m else None


def parse_date_range(date_val) -> tuple[str | None, str | None]:
    """
    Parse date_of_creation en (from, to).
    "1200-1250" → ("1200", "1250")
    "1200"      → ("1200", None)
    """
    if not date_val or (isinstance(date_val, float) and pd.isna(date_val)):
        return None, None
    s = str(date_val).strip()
    parts = s.split("-")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return s, None


def cert_mapping(certainty: str | None) -> str | None:
    """Convertit les valeurs Heurist en valeurs TEI @cert."""
    mapping = {
        "Probable":    "medium",
        "Unlikely":    "low",
        "Very likely": "high",
    }
    return mapping.get(certainty) if certainty else None


# ── Construction du modèle Pydantic depuis un groupe de lignes ─

def group_to_text_model(group: pd.DataFrame) -> Text:
    """
    Construit un objet Pydantic Text depuis un groupe de lignes
    (toutes les lignes d'un même text H-ID, une par stemma associé).
    """
    row = group.iloc[0]    # données communes au text (première ligne)
    hid = str(int(row["H-ID"]))

    # ── FileDesc ──────────────────────────────────────────────
    title_stmt = TitleStmt(
        titles=[Title(value=val(row, "preferred_name") or f"Text {hid}")],
        authors=[Author(
            name=val(row, "author_freetext"),
        )] if val(row, "author_freetext") else [],
    )

    # listWit : construit depuis les witness H-ID liés
    witnesses = []
    witness_hids = val(row, "witness H-ID")
    if witness_hids:
        try:
            import ast
            hids = ast.literal_eval(witness_hids) if isinstance(witness_hids, str) else witness_hids
            for w_hid in (hids if isinstance(hids, list) else [hids]):
                if w_hid and not pd.isna(w_hid):
                    witnesses.append(Witness(xml_id=f"hid_{int(w_hid)}"))
        except Exception:
            pass

    source_desc = SourceDesc(
        list_wit=ListWit(witnesses=witnesses) if witnesses else None
    )

    file_desc = FileDesc(title_stmt=title_stmt, source_desc=source_desc)

    # ── EncodingDesc / classDecl ──────────────────────────────
    # Les taxonomies sont déclarées une fois par fichier text
    encoding_desc = EncodingDesc(class_decl=ClassDecl(taxonomies=[
        Taxonomy(xml_id="genre",          categories=[]),
        Taxonomy(xml_id="litterary-form", categories=[]),
        Taxonomy(xml_id="versification",  categories=[]),
        Taxonomy(xml_id="rhyme",          categories=[]),
        Taxonomy(xml_id="stanza",         categories=[]),
    ]))

    # ── ProfileDesc ───────────────────────────────────────────

    # langUsage
    lang_col = val(row, "language_COLUMN")
    language = Language(
        ident=extract_lang_code(lang_col) if lang_col else None,
        value=extract_lang_label(lang_col) if lang_col else None,
        langs=[
            Lang(n="regional", value=val(row, "regional_writing_style H-ID")),
            Lang(n="scripta",  value=val(row, "scripta_freetext")),
        ],
    )
    lang_usage = LangUsage(languages=[language])

    # creation
    from_, to = parse_date_range(row.get("date_of_creation"))
    date = Date(
        from_=from_,
        to=to,
        source=val(row, "date_of_creation_source"),
        cert=cert_mapping(val(row, "date_of_creation_certainty")),
        value=val(row, "date_freetext"),
    )
    place = PlaceName(
        value=val(row, "place_of_creation_source"),
    )
    creation = Creation(date=date, place_name=place if place.value else None)

    # textClass : catRef pour chaque attribut de classification
    cat_refs = []
    for scheme, field in [
        ("genre",         "preferred_name_genre"),
        ("litterary-form","literary_form"),
        ("versification", "verse_type"),
        ("rhyme",         "rhyme_type"),
        ("stanza",        "Stanza_type"),
    ]:
        v = val(row, field)
        if v:
            slug = v.lower().replace(" ", "-")
            cat_refs.append(CatRef(scheme=f"#{scheme}", target=f"#{slug}"))

    text_class = TextClass(cat_refs=cat_refs) if cat_refs else None

    # textDesc
    derivation = Derivation(
        value=val(row, "nature_of_derivations"),
        corresp=f"hid_{val(row, 'is_derived_from H-ID')}"
                if val(row, "is_derived_from H-ID") else None,
    )
    text_desc = TextDesc(
        derivation=derivation if (derivation.value or derivation.corresp) else None,
    )

    profile_desc = ProfileDesc(
        lang_usage=lang_usage,
        creation=creation,
        text_class=text_class,
        text_desc=text_desc if text_desc.derivation else None,
    )

    # ── Body / Graph (un graphe par stemma) ───────────────────
    graphs = []
    for _, stemma_row in group.iterrows():
        openstemmata_id = val(stemma_row, "openstemmata id")
        if not openstemmata_id:
            continue
        graphs.append(Graph(
            xml_id=openstemmata_id,
            type=val(stemma_row, "stemmaType"),
            label=val(stemma_row, "text title freetext"),
        ))

    text_body = TextBody(body=Body(graphs=graphs)) if graphs else None

    return Text(
        xml_id=f"hid_{hid}",
        file_desc=file_desc,
        encoding_desc=encoding_desc,
        profile_desc=profile_desc,
        text_body=text_body,
    )


# ── Sérialisation du modèle Pydantic en XML TEI ───────────────

def text_to_xml(text: Text) -> etree._Element:
    """
    Convertit un objet Text en arbre XML TEI.
    """
    tei = el("TEI", xml_id=text.xml_id, nsmap=NSMAP)

    # ── teiHeader ─────────────────────────────────────────────
    header = sub(tei, "teiHeader")

    # fileDesc
    file_desc_el = sub(header, "fileDesc")
    title_stmt_el = sub(file_desc_el, "titleStmt")
    for title in text.file_desc.title_stmt.titles:
        sub(title_stmt_el, "title", title.value, type=title.type)
    for author in text.file_desc.title_stmt.authors:
        author_el = sub(title_stmt_el, "author", author.name)
        if author.note:
            sub(author_el, "note", author.note)

    source_desc_el = sub(file_desc_el, "sourceDesc")
    if text.file_desc.source_desc and text.file_desc.source_desc.list_wit:
        list_wit_el = sub(source_desc_el, "listWit")
        for w in text.file_desc.source_desc.list_wit.witnesses:
            sub(list_wit_el, "witness", xml_id=w.xml_id)

    # encodingDesc
    if text.encoding_desc:
        enc_el = sub(header, "encodingDesc")
        class_decl_el = sub(enc_el, "classDecl")
        for taxonomy in text.encoding_desc.class_decl.taxonomies:
            tax_el = sub(class_decl_el, "taxonomy", xml_id=taxonomy.xml_id)
            for cat in taxonomy.categories:
                cat_el = sub(tax_el, "category", xml_id=cat.xml_id)
                if cat.desc:
                    sub(cat_el, "desc", cat.desc)

    # profileDesc
    if text.profile_desc:
        prof_el = sub(header, "profileDesc")
        pd_ = text.profile_desc

        # langUsage
        if pd_.lang_usage:
            lang_usage_el = sub(prof_el, "langUsage")
            for lang in pd_.lang_usage.languages:
                lang_el = sub(lang_usage_el, "language", lang.value, ident=lang.ident)
                for l in lang.langs:
                    if l.value:
                        sub(lang_el, "lang", l.value, n=l.n)

        # creation
        if pd_.creation:
            creation_el = sub(prof_el, "creation")
            d = pd_.creation.date
            if d:
                attrs = {}
                if d.from_:   attrs["from"]   = d.from_
                if d.to:      attrs["to"]     = d.to
                if d.cert:    attrs["cert"]   = d.cert
                if d.source:  attrs["source"] = d.source
                sub(creation_el, "date", d.value, **attrs)
            if pd_.creation.place_name and pd_.creation.place_name.value:
                sub(creation_el, "placeName",
                    pd_.creation.place_name.value,
                    source=pd_.creation.place_name.source)

        # textClass
        if pd_.text_class:
            text_class_el = sub(prof_el, "textClass")
            for kw in pd_.text_class.keywords:
                kw_el = sub(text_class_el, "keywords")
                sub(kw_el, "term", kw.term.value)
            for cr in pd_.text_class.cat_refs:
                sub(text_class_el, "catRef",
                    scheme=cr.scheme, target=cr.target)

        # textDesc
        if pd_.text_desc:
            text_desc_el = sub(prof_el, "textDesc")
            if pd_.text_desc.derivation:
                drv = pd_.text_desc.derivation
                sub(text_desc_el, "derivation", drv.value, corresp=drv.corresp)

        # particDesc
        if pd_.partic_desc and pd_.partic_desc.list_person:
            partic_el = sub(prof_el, "particDesc")
            list_person_el = sub(partic_el, "listPerson")
            for person in pd_.partic_desc.list_person.persons:
                person_el = sub(list_person_el, "person", role=person.role)
                if person.p:
                    sub(person_el, "p", person.p)

    # ── text / body / graph ───────────────────────────────────
    text_el = sub(tei, "text")
    body_el = sub(text_el, "body")

    if text.text_body:
        for graph in text.text_body.body.graphs:
            graph_el = sub(body_el, "graph",
                           xml_id=graph.xml_id,
                           type=graph.type or "unknown")
            if graph.label:
                sub(graph_el, "label", graph.label)
            for node in graph.nodes:
                node_el = sub(graph_el, "node", xml_id=node.xml_id)
                if node.label:
                    sub(node_el, "label", node.label)
            for arc in graph.arcs:
                arc_el = sub(graph_el, "arc")
                if arc.from_:
                    arc_el.set("from", arc.from_)
                if arc.to:
                    arc_el.set("to", arc.to)
                if arc.label:
                    sub(arc_el, "label", arc.label)

    return tei


# ── Écriture sur disque ───────────────────────────────────────

def serialize_texts(texts_df: pd.DataFrame, output_dir: Path) -> None:
    """
    Sérialise chaque text du DataFrame en un fichier TEI XML.
    Groupe d'abord par H-ID pour rassembler les lignes multi-stemma.
    Produit un fichier hid_{H-ID}.xml par text dans output_dir.

    Args:
        texts_df   : DataFrame produit par build_texts()
        output_dir : dossier de sortie (créé si absent)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Grouper par H-ID du text (relation N-N avec stemma déjà explosée)
    groups = texts_df.groupby("H-ID")
    total   = len(groups)
    success = 0

    for hid, group in groups:
        try:
            model    = group_to_text_model(group)
            xml_root = text_to_xml(model)

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
            log.error(f"  [!] Erreur pour text H-ID {hid} : {e}")

    log.info(f"  {success}/{total} fichier(s) text produit(s) dans {output_dir}")
