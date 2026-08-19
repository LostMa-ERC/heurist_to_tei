from pydantic import BaseModel, Field
from typing import Optional, Literal

class Settlement(BaseModel):
    name: Optional[str] = None
    heurist_id: Optional[int] = None


class Repository(BaseModel):
    name: Optional[str] = None
    type: Literal["preferred_name", "label_name"]
    heurist_id: Optional[int] = None
    viaf: Optional[str] = None


class Idno(BaseModel):
    value: str
    type: Literal["heurist", "shelfmark", "old-shelfmark"]


class AltIdentifier(BaseModel):
    type: Literal["old-shelfmark"]
    idno: Idno


class Location(BaseModel):
    known: Literal["yes", "no"]


class Collection(BaseModel):
    type: Literal["yes", "no", "unknown"]
    location: Optional[Location] = None


class MsIdentifier(BaseModel):
    settlement: Optional[Settlement] = None
    repository: Optional[Repository] = None
    idnos: list[Idno] = []
    alt_identifier: Optional[AltIdentifier] = None
    collection: Optional[Collection] = None  # uniquement pour msFrag

class Dimensions(BaseModel):
    height: Optional[float] = None
    width: Optional[float] = None
    unit: Optional[str] = None
    at_least: Optional[float] = None  # uniquement pour leaves


class Layout(BaseModel):
    type: Literal["columns", "writtenLines"]
    leaves: Optional[Dimensions] = None
    written: Optional[Dimensions] = None
    written_lines: Optional[int] = None


class LayoutDesc(BaseModel):
    layouts: list[Layout] = []


class Support(BaseModel):
    material: Optional[str] = None
    form: Optional[str] = None


class SupportDesc(BaseModel):
    support: Support


class ObjectDesc(BaseModel):
    support_desc: SupportDesc
    layout_desc: LayoutDesc


class HandNote(BaseModel):
    script_type: Optional[str] = None
    script: Optional[str] = None  # subscript_type


class HandDesc(BaseModel):
    hand_note: Optional[HandNote] = None


class DecoNote(BaseModel):
    type: Literal[
        "unknown", "initials", "rubrication",
        "incomplete-dec.", "no-decoration", "unrelated-picture"
    ]


class DecoDesc(BaseModel):
    deco_note: Optional[DecoNote] = None


class PhysDesc(BaseModel):
    object_desc: ObjectDesc
    hand_desc: Optional[HandDesc] = None
    deco_desc: Optional[DecoDesc] = None

class Locus(BaseModel):
    from_: Optional[str] = Field(None, alias="from")  
    to: str

    model_config = {"populate_by_name": True}


class MsItemStruct(BaseModel):
    locus: Locus


class MsContents(BaseModel):
    ms_item_structs: list[MsItemStruct] = []

class Bibl(BaseModel):
    type: Literal["digitisation"]
    idno: Idno
    iiif_target: Optional[str] = None  # ptr/@target


class Surrogates(BaseModel):
    bibl_list: list[Bibl] = []


class Additional(BaseModel):
    surrogates: Surrogates

class MsFrag(BaseModel):
    ms_identifier: MsIdentifier
    phys_desc: Optional[PhysDesc] = None
    ms_contents: Optional[MsContents] = None
    additional: Optional[Additional] = None

class MsDesc(BaseModel):
    type: Literal["citation", "complete", "defective", "fragmentary", "lost", "unknown"]
    ms_identifier: MsIdentifier
    note: Optional[str] = None  
    ms_contents: Optional[MsContents] = None
    ms_frags: list[MsFrag] = []

class TitleStmt(BaseModel):
    title: str


class Lang(BaseModel):
    n: Literal["regional", "scripta"]
    value: Optional[str] = None


class Language(BaseModel):
    ident: Optional[str] = None
    value: Optional[str] = None
    langs: list[Lang] = []


class LangUsage(BaseModel):
    language: Language


class Date(BaseModel):
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    cert: Optional[Literal["medium", "low", "high", "unknown"]] = None
    source: Optional[str] = None
    value: Optional[str] = None
    


class Creation(BaseModel):
    date: Date

class Witness(BaseModel):
    xml_id: str
    title_stmt: TitleStmt
    lang_usage: LangUsage
    creation: Creation
    ms_desc: MsDesc