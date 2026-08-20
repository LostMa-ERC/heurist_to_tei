# -*- coding: utf-8 -*-
"""
witness_builder.py

Construit la table witness enrichie pour la pipeline heurist_to_tei,
en agrégeant les données issues des tables Heurist : Witness, Part,
DocumentTable, Digitization, Repository et PhysDesc.

Credits : Virgile Reignier pour Heurist analyzer.
"""

import pandas as pd
from lostma_db import LostmaDB


def build_witnesses(db: LostmaDB, available_languages: list[str]) -> pd.DataFrame:
    """
    Reconstruit la table witness à partir de la base Heurist, enrichie
    des attributs liés de Part, DocumentTable et PhysDesc, en excluant
    les colonnes issues de TextTable, Genre et Story.

    Args:
        db: instance LostmaDB déjà synchronisée (db.sync() doit avoir
            été appelé au préalable).
        available_languages: liste des langues à filtrer, ex.
            ["dum (Middle Dutch)", "enm (Middle English)"].

    Returns:
        DataFrame witness nettoyé et enrichi.
    """
    # Récupération de l'objet witness avec les tables liées.
    # Les arguments 0, 0 permettent de ne pas dropper les colonnes peu
    # remplies, contrairement à la release de Virgile.
    witnesses_full = db.witnesses(available_languages, 0, 0)

    # Suppression des colonnes issues de TextTable, Genre et Story :
    # ces données sont gérées par le builder text_builder.py et ne
    # doivent pas être dupliquées ici.
    cols_to_drop = [
        col for col in witnesses_full.columns
        if col.startswith("TextTable_")
        or col.startswith("Genre_")
        or col.startswith("Story_")
    ]


    witnesses = witnesses_full.drop(
        columns=[col for col in cols_to_drop if col in witnesses_full.columns]
    )

    witnesses = witnesses.explode("Witness_observed_on_pages H-ID", ignore_index=False)

    # Ajout des attributs liés de Part.
    # Renommage de DocumentTable_H-ID en Witness_last_observed_in_doc H-ID
    # pour faciliter la jointure.

    parts_data = db.parts(available_languages, 0, 0)

    witnesses["Witness_observed_on_pages H-ID"] = witnesses["Witness_observed_on_pages H-ID"].astype(str)
    parts_data["Part_H-ID"] = parts_data["Part_H-ID"].astype(str)
   
    
    witnesses = witnesses.merge(
        parts_data,
        left_on="Witness_observed_on_pages H-ID", 
        right_on="Part_H-ID",
        how="left",
        suffixes=("_witness", "_part"),
    )
    print(f"DEBUG: after Part merge, shape = {witnesses.shape}")


    # Ajout des attributs liés de PhysDesc.
    # Attention : PhysDesc n'existe à ce jour que pour les données
    # scrappées depuis Jonas (corpus français). Pour dum et enm, les
    # colonnes seront vides. A REVOIR si de nouvelles sources sont
    # ajoutées au pipeline.
    
    # physdesc_data = db.table("PhysDesc")
    # physdesc_data_renamed = physdesc_data.rename(
    #     columns={"subject_of_description H-ID": "Witness_H-ID"}
    # )

    # witnesses = witnesses.merge(
    #     physdesc_data_renamed,
    #     on="Witness_H-ID",
    #     how="left",
    #     suffixes=("", "_physdesc"),
    # )

    # Nettoyage final : suppression des colonnes inutiles
    # (review, IDs techniques, doublons d'attributs witness).
    cols_to_clean = [
        "Witness_last_observed_in_doc Name",
        "Witness_is_unobserved",
        "Witness_claim_freetext",
        "Witness scribe H-ID",
        "Witness scribe Name",
        "Witness_number_of_hands",
        "Witness_scribe_note",
        "Witness place_of_creation H-ID",
        "Witness place_of_creation Name",
        "Witness_place_of_creation_source",
        "H-ID",
        "type_id",
        "has_decorations TRM-ID",
        "amount_of_illustrations TRM-ID",
        "above_top_line TRM-ID",
        "script_type TRM-ID",
        "subscript_type TRM-ID",
    ] + [col for col in witnesses.columns if col.startswith("review_")]

    print(f"DEBUG: cols_to_clean count = {len(cols_to_clean)}") 
    print(f"DEBUG: cols_to_clean available = {len([col for col in cols_to_clean if col in witnesses.columns])}")

    witnesses = witnesses.drop(
        columns=[col for col in cols_to_clean if col in witnesses.columns]
    )


    return witnesses



if __name__ == "__main__":
    # Exécution autonome pour test / debug rapide en ligne de commande.
    import os
    from dotenv import load_dotenv

    load_dotenv()
    login = os.getenv("HEURIST_LOGIN")
    pwd = os.getenv("HEURIST_PASSWORD")

    db = LostmaDB(login, pwd)
    db.sync()

    available_languages = ["dum (Middle Dutch)", "enm (Middle English)"]
    witnesses = build_witnesses(db, available_languages)

    print(witnesses.columns.tolist())
    print(witnesses.head())
