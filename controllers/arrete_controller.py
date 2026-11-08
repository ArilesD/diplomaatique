from flask import Blueprint, abort, render_template, request

from models.arrete_modele import ArreteModele

blueprint_arretes = Blueprint("arretes", __name__)
modele_arrete = ArreteModele()


@blueprint_arretes.route("/")
def page_accueil():
    """Page principale: liste + recherche + filtres."""
    mot_cle = request.args.get("q", "").strip()
    prefecture = request.args.get("prefecture", "").strip()
    annee = request.args.get("annee", "").strip()
    date_publication = request.args.get("date", "").strip()
    annees_disponibles = modele_arrete.recuperer_annees_disponibles(prefecture=prefecture)
    if annee and annee not in set(annees_disponibles):
        annee = ""

    dates_disponibles = modele_arrete.recuperer_dates_disponibles(
        prefecture=prefecture,
        annee=annee,
    )

    # On n'accepte que les dates réellement disponibles.
    if date_publication and date_publication not in set(dates_disponibles):
        date_publication = ""

    liste_arretes = modele_arrete.rechercher_arretes(
        mot_cle=mot_cle,
        prefecture=prefecture,
        date_publication=date_publication,
        annee=annee,
    )
    liste_prefectures = modele_arrete.recuperer_prefectures()

    return render_template(
        "index.html",
        arretes=liste_arretes,
        nb_resultats=len(liste_arretes),
        prefectures=liste_prefectures,
        annees_disponibles=annees_disponibles,
        dates_disponibles=dates_disponibles,
        filtres={
            "q": mot_cle,
            "prefecture": prefecture,
            "annee": annee,
            "date": date_publication,
        },
    )


@blueprint_arretes.route("/arrete/<int:arrete_id>")
def detail_arrete(arrete_id: int):
    """Page détail d'un arrêté."""
    detail = modele_arrete.recuperer_detail_arrete(arrete_id)
    if not detail:
        abort(404)
    return render_template("detail.html", detail=detail)
