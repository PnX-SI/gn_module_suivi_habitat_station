'''
   Spécification du schéma toml des paramètres de configurations
'''

from marshmallow import Schema, fields

export_available_format = ['geojson', 'csv', 'shapefile']

id_type_commune = 25
zoom_center = [44.863664, 6.268670]
zoom= 10
pagination_serverside= False
items_per_page = 10
plot_size_unite = "mètres"
MODULE_CODE = "SUIVI_HAB_STA"
id_nomenclature_type_site = 773
id_bib_list_habitat = 2

site_message = {"emptyMessage" : "Aucun site à afficher ", "totalMessage" : "sites(s) au total"}
list_visit_message = {"emptyMessage" : "Aucune visite sur ce site ", "totalMessage" : "visites au total"}
detail_list_visit_message = {"emptyMessage" : "Aucune autre visite sur ce site ", "totalMessage" : "visites au total"}
default_site_columns = [
    { "name" : "Identifiant", "prop" : "id_base_site", "width" : "90"},
    { "name" : "Habitat", "prop" : "nom_habitat", "width" : "350"},
    { "name" : "Nombre de visites", "prop" : "nb_visit", "width" : "120"},
    { "name" : "Date de la dernière visite", "prop" : "date_max", "width" : "160"}
]

default_list_visit_columns = [
    { "name" : "Date", "prop" : "visit_date_min", "width": "120"},
    { "name" : "Observateur(s)", "prop" : "observers", "width": "350"}
]
id_menu_list_user = 1

class GnModuleSchemaConf(Schema):
    site_message=fields.Dict(missing=site_message)
    list_visit_message = fields.Dict(missing=list_visit_message)
    detail_list_visit_message = fields.Dict(missing=detail_list_visit_message)
    export_available_format = fields.List(fields.String(), missing=export_available_format)
    default_site_columns = fields.List(fields.Dict(), missing=default_site_columns)
    default_list_visit_columns = fields.List(fields.Dict(), missing=default_list_visit_columns)
    id_type_commune = fields.Integer(missing=25)
    id_menu_list_user = fields.Integer(missing=1)
    export_srid = fields.Integer(missing=2154)
    zoom_center = fields.List(fields.Float(), missing=zoom_center)
    zoom=fields.Integer(missing=10)
    pagination_serverside = fields.Boolean(missing=pagination_serverside)
    items_per_page = fields.Integer(missing=items_per_page)
    plot_size_unite = fields.String(missing=plot_size_unite)
    id_nomenclature_type_site = fields.Integer(missing=id_nomenclature_type_site)
    id_bib_list_habitat = fields.Integer(missing=id_bib_list_habitat)
   
