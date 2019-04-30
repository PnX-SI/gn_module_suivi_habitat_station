import json
import datetime

from flask import Blueprint, request, session, current_app, send_from_directory, abort, jsonify
from geojson import FeatureCollection, Feature
from sqlalchemy.sql.expression import func
from sqlalchemy import and_, distinct, desc
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2.shape import to_shape

from pypnusershub.db.tools import InsufficientRightsError
from pypnnomenclature.models import TNomenclatures
from pypnusershub.db.models import User

from geonature.utils.env import DB, ROOT_DIR
from geonature.utils.utilsgeometry import FionaShapeService
from geonature.utils.utilssqlalchemy import json_resp, to_json_resp, to_csv_resp
from geonature.core.gn_permissions import decorators as permissions
from geonature.core.gn_permissions.tools import get_or_fetch_user_cruved
from geonature.core.gn_monitoring.models import corVisitObserver, corSiteArea, corSiteModule, TBaseVisits
from geonature.core.ref_geo.models import LAreas
from geonature.core.users.models import BibOrganismes


from .repositories import check_user_cruved_visit, check_year_visit

from .models import HabrefSHS, TTransect, TPlot, TRelevePlot, TVisitSHS, CorTransectVisitPerturbation, CorRelevePlotStrat, CorRelevePlotTaxon, Taxonomie, CorHabTaxon

blueprint = Blueprint('pr_monitoring_habitat_station', __name__)


@blueprint.route('/sites', methods=['GET'])
@json_resp
def get_all_sites():
    '''
    Retourne tous les sites
    '''
    parameters = request.args
    print('params', parameters)

    q = (
        DB.session.query(
            TTransect,
            func.max(TBaseVisits.visit_date_min),
            HabrefSHS.lb_hab_fr_complet,
            func.count(distinct(TBaseVisits.id_base_visit)),
            func.string_agg(distinct(BibOrganismes.nom_organisme), ', ')
        ).outerjoin(
            TBaseVisits, TBaseVisits.id_base_site == TTransect.id_base_site
        )
        # get habitat
        .outerjoin(
            HabrefSHS, TTransect.cd_hab == HabrefSHS.cd_hab
        )
        # get organisme
        .outerjoin(
            corVisitObserver, corVisitObserver.c.id_base_visit == TBaseVisits.id_base_visit
        ).outerjoin(
            User, User.id_role == corVisitObserver.c.id_role
        ).outerjoin(
            BibOrganismes, BibOrganismes.id_organisme == User.id_organisme
        )
        .group_by(
            TTransect, HabrefSHS.lb_hab_fr_complet
        )
    )

    if 'filterHab' in parameters:
        q = q.filter(TTransect.cd_hab == parameters['filterHab'])

    if ('date_low' in parameters) and ('date_up' in parameters)  :
        q_date = (
            DB.session.query(
                TTransect.id_base_site,
                func.max(TBaseVisits.visit_date_min),
            ).outerjoin(
                TBaseVisits, TBaseVisits.id_base_site == TTransect.id_base_site
            ).group_by(TTransect.id_base_site).all()
        )
        q = q.filter(
            and_(TBaseVisits.visit_date_min <= parameters['date_up'], TBaseVisits.visit_date_min >= parameters['date_low']))

    page = request.args.get('page', 1, type=int)
    items_per_page = blueprint.config['items_per_page']
    pagination_serverside = blueprint.config['pagination_serverside']
    pagination = q.paginate(page, items_per_page, False)
    totalItmes = pagination.total
    if (pagination_serverside):
        data = pagination.items
    else:
        data = q.all()

    pageInfo = {
        'totalItmes': totalItmes,
        'items_per_page': items_per_page,
    }
    features = []

    if data:
        for d in data:
            feature = d[0].get_geofeature(True)
            id_site = feature['properties']['id_base_site']
            base_site_code = feature['properties']['t_base_site']['base_site_code']
            base_site_description = feature['properties']['t_base_site']['base_site_description'] or 'Aucune description'
            base_site_name = feature['properties']['t_base_site']['base_site_name']
            if feature['properties']['t_base_site']:
                del feature['properties']['t_base_site']

            if 'year' in parameters:
                for dy in q_date:
                    #  récupérer la bonne date max du site si on filtre sur année
                    if id_site == dy[0]:
                        feature['properties']['date_max'] = str(d[1])
            else:
                feature['properties']['date_max'] = str(d[1])
                if d[1] == None:
                    feature['properties']['date_max'] = 'Aucune visite'

            feature['properties']['nom_habitat'] = str(d[2])
            feature['properties']['nb_visit'] = str(d[3])

            if d[4] == None:
                feature['properties']['organisme'] = 'Aucun'

            feature['properties']['organisme'] = 'Aucun'
            feature['properties']['base_site_code'] = base_site_code
            feature['properties']['base_site_description'] = base_site_description
            feature['properties']['base_site_name'] = base_site_name
            features.append(feature)

        return [pageInfo, FeatureCollection(features)]
    return None


@blueprint.route('/site/<id_site>', methods=['GET'])
@json_resp
def get_site(id_site):
    '''
    Retourne un site à l'aide de son id
    '''

    id_type_commune = blueprint.config['id_type_commune']

    data = DB.session.query(
        TTransect,
        TNomenclatures,
        func.string_agg(distinct(LAreas.area_name), ', '),
        func.string_agg(distinct(BibOrganismes.nom_organisme), ', '),
        HabrefSHS.lb_hab_fr_complet
    ).filter_by(id_base_site=id_site
                ).outerjoin(
        TBaseVisits, TBaseVisits.id_base_site == TTransect.id_base_site
    ).outerjoin(
        TNomenclatures, TTransect.id_nomenclature_plot_position == TNomenclatures.id_nomenclature
        # get habitat
    ).outerjoin(
        HabrefSHS, TTransect.cd_hab == HabrefSHS.cd_hab
        # get organisme
    ).outerjoin(
        corVisitObserver, corVisitObserver.c.id_base_visit == TBaseVisits.id_base_visit
    ).outerjoin(
        User, User.id_role == corVisitObserver.c.id_role
    ).outerjoin(
        BibOrganismes, BibOrganismes.id_organisme == User.id_organisme
        # get municipalities of a site
    ).outerjoin(
        corSiteArea, corSiteArea.c.id_base_site == TTransect.id_base_site
    ).outerjoin(
        LAreas, and_(LAreas.id_area == corSiteArea.c.id_area,
                     LAreas.id_type == id_type_commune)
    ).group_by(TTransect.id_transect, TNomenclatures.id_nomenclature, HabrefSHS.lb_hab_fr_complet
               ).first()

    plots = DB.session.query(TPlot).filter_by(
        id_transect=TTransect.id_transect)

    if data:
        transect = data[0].get_geofeature(True)
        plot_position = data[1].as_dict()
        transect['properties']['plot_position'] = plot_position
        if data[2]:
            transect['properties']['nom_commune'] = str(data[2])
        if data[3]:
            transect['properties']['observers'] = str(data[3])
        if data[4]:
            transect['properties']['nom_habitat'] = str(data[4])
        if(plots):
            transect['properties']['plots'] = [p.as_dict() for p in plots]
        base_site_code = transect['properties']['t_base_site']['base_site_code']
        base_site_description = transect['properties']['t_base_site']['base_site_description'] or 'Aucune description'
        base_site_name = transect['properties']['t_base_site']['base_site_name']
        if transect['properties']['t_base_site']:
            del transect['properties']['t_base_site']
        transect['properties']['base_site_code'] = base_site_code
        transect['properties']['base_site_description'] = base_site_description
        transect['properties']['base_site_name'] = base_site_name
        return transect
    return None


@blueprint.route('/visit', methods=['POST'])
@json_resp
def post_visit():
    '''
    Poster une nouvelle visite
    '''
    data = dict(request.get_json())
    check_year_visit(data['id_base_site'], data['visit_date_min'][0:4])

    tab_releve_plots = []
    tab_observers = []
    tab_perturbations = []
    tab_plot_data = []

    if 'plots' in data:
        tab_releve_plots = data.pop('plots')
    if 'observers' in data:
        tab_observers = data.pop('observers')
    if 'perturbations' in data:
        if data['perturbations'] != None:
            tab_perturbations = data.pop('perturbations')
        else:
            data.pop('perturbations')
    visit = TVisitSHS(**data)

    for per in tab_perturbations:
        visit_per = CorTransectVisitPerturbation(**per)
        visit.cor_visit_perturbation.append(visit_per)

    for releve in tab_releve_plots:
        if 'plot_data' in releve:
            releve['excretes_presence'] = releve['plot_data']['excretes_presence']
            tab_plot_data = releve.pop('plot_data')
        releve_plot = TRelevePlot(**releve)
        for strat in tab_plot_data['strates_releve']:
            strat_item = CorRelevePlotStrat(**strat)
            releve_plot.cor_releve_strats.append(strat_item)
        for taxon in tab_plot_data['taxons_releve']:
            taxon_item = CorRelevePlotTaxon(**taxon)
            releve_plot.cor_releve_taxons.append(taxon_item)
        visit.cor_releve_plot.append(releve_plot)

    observers = DB.session.query(User).filter(
        User.id_role.in_(tab_observers)
    ).all()
    for o in observers:
        visit.observers.append(o)
    visit.as_dict(True)
    DB.session.add(visit)
    DB.session.commit()
    return visit.as_dict(recursif=True)


@blueprint.route('/site/<id_site>/visits', methods=['GET'])
@json_resp
def get_visits(id_site):
    '''
    Retourne les visites d'un site par son id
    '''
    items_per_page = blueprint.config['items_per_page']
    q = DB.session.query(TVisitSHS).filter_by(id_base_site=id_site)
    pagination = q.paginate()
    totalItmes = pagination.total
    data = q.all()
    pageInfo = {
        'totalItmes': totalItmes,
        'items_per_page': items_per_page,
    }
    if data:
        return [pageInfo, [d.as_dict(True) for d in data]]
    return None


@blueprint.route('/visit/<id_visit>', methods=['GET'])
@json_resp
def get_visitById(id_visit):
    '''
    Retourne les visites d'un site par son id
    '''
    data = DB.session.query(TVisitSHS).filter_by(
        id_base_visit=id_visit).first()
    if data:
        visit = data.as_dict(True)
        for releve in visit['cor_releve_plot']:
            print('releve', releve)
            plot_data = dict()
            plot_data['excretes_presence'] = releve['excretes_presence']
            plot_data['taxons_releve'] = releve['cor_releve_taxons']
            plot_data['strates_releve'] = releve['cor_releve_strats']
            releve['plot_data'] = plot_data
            del releve['excretes_presence']
            del releve['cor_releve_taxons']
            del releve['cor_releve_strats']
        return visit
    return None


@blueprint.route('/habitats/<cd_hab>/taxons', methods=['GET'])
@json_resp
def get_taxa_by_habitats(cd_hab):
    '''
    tous les taxons d'un habitat
    '''
    q = DB.session.query(
        CorHabTaxon.id_cor_hab_taxon,
        Taxonomie.nom_complet
    ).join(
        Taxonomie, CorHabTaxon.cd_nom == Taxonomie.cd_nom
    ).group_by(CorHabTaxon.id_habitat, CorHabTaxon.id_cor_hab_taxon, Taxonomie.nom_complet)

    q = q.filter(CorHabTaxon.id_habitat == cd_hab)
    data = q.all()

    taxons = []
    if data:
        for d in data:
            taxon = dict()
            taxon['id_cor_hab_taxon'] = str(d[0])
            taxon['nom_complet'] = str(d[1])
            taxons.append(taxon)
        return taxons
    return None


@blueprint.route('/update_visit/<id_visit>', methods=['PATCH'])
@json_resp
def patch_visit(id_visit):
    '''
    Mettre à jour une visite
    '''
    data = dict(request.get_json())
    try:
        existingVisit = TVisitSHS.query.filter_by(
            id_base_visit=id_visit).first()
        if(existingVisit == None):
            raise ValueError('This visit does not exist')
    except ValueError:
        resp = jsonify({"error": 'This visit does not exist'})
        resp.status_code = 404
        return resp

    existingVisit = existingVisit.as_dict(recursif=True)
    dateIsUp = data['visit_date_min'] != existingVisit['visit_date_min']

    if dateIsUp:
        check_year_visit(data['id_base_site'], data['visit_date_min'][0:4])

    tab_releve_plots = []
    tab_observers = []
    tab_perturbations = []
    tab_plot_data = []

    if 'plots' in data:
        tab_releve_plots = data.pop('plots')
    if 'observers' in data:
        tab_observers = data.pop('observers')
    if 'perturbations' in data:
        tab_perturbations = data.pop('perturbations')

    visit = TVisitSHS(**data)

    for releve in tab_releve_plots:
        if 'plot_data' in releve:
            releve['excretes_presence'] = releve['plot_data']['excretes_presence']
            tab_plot_data = releve.pop('plot_data')
        releve_plot = TRelevePlot(**releve)
        for strat in tab_plot_data['strates_releve']:
            strat_item = CorRelevePlotStrat(**strat)
            releve_plot.cor_releve_strats.append(strat_item)
        for taxon in tab_plot_data['taxons_releve']:
            taxon_item = CorRelevePlotTaxon(**taxon)
            releve_plot.cor_releve_taxons.append(taxon_item)

        visit.cor_releve_plot.append(releve_plot)

    DB.session.query(CorTransectVisitPerturbation).filter_by(
        id_base_visit=id_visit).delete()
    for per in tab_perturbations:
        print('perturb', per)
        visit_per = CorTransectVisitPerturbation(**per)
        visit.cor_visit_perturbation.append(visit_per)
    observers = DB.session.query(User).filter(
        User.id_role.in_(tab_observers)
    ).all()
    for o in observers:
        visit.observers.append(o)
    print('visit', visit.as_dict(recursif=True))
    mergeVisit = DB.session.merge(visit)

    DB.session.commit()

    return mergeVisit.as_dict(recursif=True)
