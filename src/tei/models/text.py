# -*- coding: utf-8 -*-
"""
src/tei/models/text.py

Modèles Pydantic pour la sérialisation TEI des données Text.
Basé sur l'ODD test_lostma_text.

Structure TEI couverte :
    TEI
    ├── teiHeader
    │   ├── fileDesc
    │   │   ├── titleStmt (title, author, principal, respStmt)
    │   │   └── sourceDesc (listWit)
    │   ├── encodingDesc (classDecl → taxonomy → category)
    │   └── profileDesc
    │       ├── langUsage (language → lang)
    │       ├── creation (date, placeName)
    │       ├── textClass (keywords → term, catRef)
    │       ├── textDesc (constitution, derivation)
    │       └── particDesc (listPerson → person)
    └── text
        └── body
            └── graph (label, node, arc)
"""

from pydantic import BaseModel
from typing import Optional, Literal


# ── titleStmt ────────────────────────────────────────────────

class Title(BaseModel):
    """
    Titre du texte.
    @type : "preferred" recommandé.
    textnode ← TextTable_preferred_name
    """
    value: str
    type: Optional[str] = "preferred"


class Author(BaseModel):
    """
    Auteur du texte.
    textnode ← TextTable_is_written_by Name
    note     ← TextTable_author_freetext
    """
    name: Optional[str] = None
    note: Optional[str] = None


class PersName(BaseModel):
    forename: str
    surname: str


class Principal(BaseModel):
    pers_name: PersName


class RespStmt(BaseModel):
    resp: str
    pers_name: PersName


class TitleStmt(BaseModel):
    titles: list[Title]
    authors: list[Author] = []
    principal: Optional[Principal] = None
    resp_stmts: list[RespStmt] = []


# ── sourceDesc / listWit ──────────────────────────────────────

class Witness(BaseModel):
    """
    Référence à un témoin dans la listWit du texte.
    @xml:id ← witness H-ID (format hid_123)
    textnode : nom ou sigle du témoin
    """
    xml_id: str
    value: Optional[str] = None


class ListWit(BaseModel):
    witnesses: list[Witness] = []


class SourceDesc(BaseModel):
    list_wit: Optional[ListWit] = None


# ── encodingDesc / classDecl ──────────────────────────────────

class Category(BaseModel):
    """
    @xml:id ← valeur normalisée (ex. "arthurian-romance")
    desc    ← texte descriptif (pattern A) ou absent (pattern B)
    """
    xml_id: str
    desc: Optional[str] = None


class Taxonomy(BaseModel):
    """
    @xml:id ← nom de la taxonomie
              ("genre", "litterary-form", "versification", "rhyme", "stanza")
    """
    xml_id: Literal["genre", "litterary-form", "versification", "rhyme", "stanza"]
    categories: list[Category] = []


class ClassDecl(BaseModel):
    taxonomies: list[Taxonomy] = []


class EncodingDesc(BaseModel):
    class_decl: ClassDecl


# ── profileDesc / langUsage ───────────────────────────────────

class Lang(BaseModel):
    """
    @n      : "regional" ou "scripta"
    textnode ← TextTable_regional_writing_style (regional)
               TextTable_scripta_freetext (scripta)
    """
    n: Literal["regional", "scripta"]
    value: Optional[str] = None


class Language(BaseModel):
    """
    @ident  ← code ISO extrait de TextTable_language_COLUMN
               ex. "dum (Middle Dutch)" → "dum"
    textnode ← libellé long ex. "Middle Dutch"
    langs    ← régional + scripta
    note     ← optionnel
    """
    ident: Optional[str] = None
    value: Optional[str] = None
    langs: list[Lang] = []
    note: Optional[str] = None


class LangUsage(BaseModel):
    languages: list[Language] = []


# ── profileDesc / creation ────────────────────────────────────

class Date(BaseModel):
    """
    @from   ← TextTable_date_of_creation (borne basse)
    @to     ← TextTable_date_of_creation (borne haute)
    @source ← TextTable_date_of_creation_source
    @cert   ← TextTable_date_of_creation_certainty
    textnode ← TextTable_date_freetext
    """
    from_: Optional[str] = None    # alias "from" (mot réservé Python)
    to: Optional[str] = None
    source: Optional[str] = None
    cert: Optional[Literal["low", "medium", "high"]] = None
    value: Optional[str] = None    # date_freetext

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}


class PlaceName(BaseModel):
    """
    textnode ← Place_place_of_creation
    @source  ← TextTable_place_of_creation_source
    """
    value: Optional[str] = None
    source: Optional[str] = None


class Creation(BaseModel):
    date: Optional[Date] = None
    place_name: Optional[PlaceName] = None


# ── profileDesc / textClass ───────────────────────────────────

class Term(BaseModel):
    """
    textnode ← TextTable_literary_form (mixed, prose, verse)
    """
    value: str


class Keywords(BaseModel):
    term: Term


class CatRef(BaseModel):
    """
    @scheme ← xml:id de la taxonomy (ex. "#genre")
    @target ← xml:id de la category (ex. "#arthurian-romance")
    Encode : literary_form, verse_type, rhyme_type, stanza_type
    """
    scheme: Optional[str] = None
    target: Optional[str] = None


class TextClass(BaseModel):
    keywords: list[Keywords] = []
    cat_refs: list[CatRef] = []


# ── profileDesc / textDesc ────────────────────────────────────

class Constitution(BaseModel):
    """
    ← Witness_status_witness (complete, defective, fragmentary…)
    """
    type: Optional[str] = None


class Derivation(BaseModel):
    """
    textnode ← TextTable_nature_of_derivations
    @corresp ← TextTable_is_derived_from H-ID (format hid_123)
    """
    value: Optional[str] = None
    corresp: Optional[str] = None


class TextDesc(BaseModel):
    constitution: Optional[Constitution] = None
    derivation: Optional[Derivation] = None


# ── profileDesc / particDesc ──────────────────────────────────

class Person(BaseModel):
    """
    @role   : "author"
    p       ← données sur la personne
    """
    role: str
    p: Optional[str] = None


class ListPerson(BaseModel):
    persons: list[Person] = []


class ParticDesc(BaseModel):
    list_person: Optional[ListPerson] = None


# ── profileDesc ───────────────────────────────────────────────

class ProfileDesc(BaseModel):
    lang_usage: Optional[LangUsage] = None
    creation: Optional[Creation] = None
    text_class: Optional[TextClass] = None
    text_desc: Optional[TextDesc] = None
    partic_desc: Optional[ParticDesc] = None


# ── teiHeader ────────────────────────────────────────────────

class TeiHeader(BaseModel):
    file_desc: Optional[object] = None    # titleStmt + sourceDesc
    encoding_desc: Optional[EncodingDesc] = None
    profile_desc: Optional[ProfileDesc] = None


# ── body / graph ──────────────────────────────────────────────

class Arc(BaseModel):
    """
    Représente une relation dans le graphe du stemma.
    @from ← nœud source
    @to   ← nœud cible
    """
    from_: Optional[str] = None
    to: Optional[str] = None
    label: Optional[str] = None

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}


class Node(BaseModel):
    """
    Représente un nœud (witness ou ancêtre) dans le graphe du stemma.
    @xml:id : identifiant du nœud
    """
    xml_id: str
    label: Optional[str] = None


class Graph(BaseModel):
    """
    Représente un stemma codicum.
    @xml:id ← openstemmata_id
    @type   ← stemmaType (ex. "contamination", "unknown")
    """
    xml_id: str
    type: Optional[str] = None
    label: Optional[str] = None
    nodes: list[Node] = []
    arcs: list[Arc] = []


class Body(BaseModel):
    graphs: list[Graph] = []


class TextBody(BaseModel):
    body: Body


# ── Modèle racine ─────────────────────────────────────────────

class FileDesc(BaseModel):
    title_stmt: TitleStmt
    source_desc: Optional[SourceDesc] = None


class Text(BaseModel):
    """
    Modèle racine pour un fichier TEI Text LostMa.

    @xml:id ← TextTable H-ID (format hid_123)

    Remarques :
    - listWit est alimenté par OpenStemmata (witness H-IDs liés au texte)
    - classDecl (taxonomies) est généré une fois et partagé entre tous les textes
    - graph dans body est produit depuis les données Stemma + OpenStemmata
    """
    xml_id: str
    file_desc: FileDesc
    encoding_desc: Optional[EncodingDesc] = None
    profile_desc: Optional[ProfileDesc] = None
    text_body: Optional[TextBody] = None