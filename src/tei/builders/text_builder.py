# -*- coding: utf-8 -*-
"""
text_builder.py

Construit la table text enrichie pour la pipeline heurist_to_tei,
en agrégeant les données issues des tables Heurist : TextTable, Genre,
Story, Storyverse et Stemma.
"""

import pandas as pd
from lostma_db import LostmaDB
from pathlib import Path

def build_texts(
    db: LostmaDB,
    available_languages: list[str],
    tei_output_path: Path | None = None,    
) -> pd.DataFrame:
    """
    Reconstruit la table text à partir de la base Heurist, enrichie
    des attributs liés de Genre, Story, Storyverse et Stemma.

    Args:
        db: instance LostmaDB déjà synchronisée (db.sync() doit avoir
            été appelé au préalable).
        available_languages: liste des langues à filtrer, ex.
            ["dum (Middle Dutch)", "enm (Middle English)"].

    Retourne :
        DataFrame text nettoyé et enrichi.
    """
    texts = db.texts(available_languages)

    # Pas de méthode dédiée pour Genre dans LostmaDB, donc récupération
    # manuelle de la table puis merge sur specific_genre H-ID.
    genre = db.table("Genre")

    texts = texts.merge(
        genre.rename(columns={"H-ID": "specific_genre H-ID"}),
        on="specific_genre H-ID",
        how="left",
        suffixes=("", "_genre"),
    )

    # Liaison via is_expression_of H-ID (text) -> H-ID (story).
    # Cette colonne est un INTEGER[] côté text, donc explode + cast
    # sont nécessaires avant le merge.
    story = db.table("Story")[["H-ID", "preferred_name", "is_part_of_storyverse H-ID"]]

    story["H-ID"] = story["H-ID"].astype("Int64")

    import ast

    texts["is_expression_of H-ID"] = texts["is_expression_of H-ID"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else x
    )
    texts = texts.explode("is_expression_of H-ID")
    texts["is_expression_of H-ID"] = texts["is_expression_of H-ID"].astype("Int64")
    story["H-ID"] = story["H-ID"].astype("Int64")

    texts = texts.merge(
        story.rename(columns={
            "H-ID": "is_expression_of H-ID",
            "preferred_name": "story_preferred_name",
            "is_part_of_storyverse H-ID": "story_is_part_of_storyverse H-ID",
        }),
        on="is_expression_of H-ID",
        how="left",
    )

    # Liaison via story_is_part_of_storyverse H-ID -> H-ID (storyverse).
    # Même logique explode + cast, la colonne story_is_part_of_storyverse
    # H-ID est elle-même un INTEGER[] côté Story.
    storyverse = db.table("Storyverse")[["H-ID", "preferred_name"]]
    
    storyverse["H-ID"] = storyverse["H-ID"].astype("Int64")
    
    import ast
    
    texts["story_is_part_of_storyverse H-ID"] = texts["story_is_part_of_storyverse H-ID"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else x
    )
    texts = texts.explode("story_is_part_of_storyverse H-ID")
    texts["story_is_part_of_storyverse H-ID"] = texts["story_is_part_of_storyverse H-ID"].astype("Int64")

    texts = texts.merge(
        storyverse.rename(columns={
            "H-ID": "story_is_part_of_storyverse H-ID",
            "preferred_name": "storyverse_preferred_name",
        }),
        on="story_is_part_of_storyverse H-ID",
        how="left",
    )

    # Liaison via in_stemma H-ID -> H-ID (stemma).
    stemma = db.table("Stemma")

    texts = texts.explode("in_stemma H-ID")
    texts["in_stemma H-ID"] = texts["in_stemma H-ID"].astype("Int64")
    stemma["H-ID"] = stemma["H-ID"].astype("Int64")

    texts = texts.merge(
        stemma.rename(columns={"H-ID": "in_stemma H-ID"}),
        on="in_stemma H-ID",
        how="left",
        suffixes=("", "_stemma"),
    )

    # dernier nettoyage :

    # Vérifier la liste exacte des colonnes via texts.columns avant
    # d'ajuster cette liste si la structure du dataframe a changé.
    cols_to_drop = [
        col for col in texts.columns if "review_" in col or "TRM-ID" in col
    ] + [
        "claim_freetext",
        "peripheral",
        "has_lost_older_version",
        "ancient_translations_freetext",
        "rewritings_freetext",
        "note",
        "is_adapted_by H-ID",
        "described_by_source H-ID",
        "described_at_URL",
        "reference_notes",
    ]

    texts = texts.drop(columns=[col for col in cols_to_drop if col in texts.columns])

    if tei_output_path is not None:
        from src.tei.openstemmata import fetch_and_integrate_from_df
        fetch_and_integrate_from_df(
            texts_df=texts,
            target_tei_path=tei_output_path,
            output_path=tei_output_path.parent / "enriched.xml",
        )


    return texts


if __name__ == "__main__":
    # Exécution autonome pour test / debug rapide en ligne de commande.
    import os
    from dotenv import load_dotenv

    load_dotenv()
    login = os.getenv("HEURIST_LOGIN")
    pwd = os.getenv("HEURIST_PASSWORD")

    db = LostmaDB(login, pwd)
    db.sync()

    available_languages = ["pro (Occitan)"]
    texts = build_texts(db, available_languages)

    print(texts.columns.tolist())
    print(texts.head())
