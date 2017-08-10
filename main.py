# -*- coding:utf-8 -*-
import requests
import config

import os
import sys, collections
from empty import Empty
from flask import Flask, render_template, g, session, redirect, url_for, request, flash, abort, Response, stream_with_context
import flask_ld as ld
from flask_ld.utils import lru
from flask_restful import Resource
from nanopub import NanopublicationManager, Nanopublication
import requests
from re import finditer

from flask_admin import Admin, BaseView, expose

import rdflib
from flask_security import Security, \
    UserMixin, RoleMixin, login_required
from flask_security.core import current_user
from flask_login import AnonymousUserMixin, login_user
from flask_security.forms import RegisterForm
from flask_security.utils import encrypt_password
from werkzeug.datastructures import ImmutableList
from flask_wtf import Form, RecaptchaField
from wtforms import TextField, TextAreaField, StringField, validators
import rdfalchemy
from rdfalchemy.orm import mapper
import sadi
import json
import sadi.mimeparse

from flask_mail import Mail, Message

from celery import Celery
from celery.schedules import crontab

import database

from datetime import datetime

import markdown

import rdflib.plugin
from rdflib.store import Store
from rdflib.parser import Parser
from rdflib.serializer import Serializer
from rdflib.query import ResultParser, ResultSerializer, Processor, Result, UpdateProcessor
from rdflib.exceptions import Error
rdflib.plugin.register('sparql', Result,
        'rdflib.plugins.sparql.processor', 'SPARQLResult')
rdflib.plugin.register('sparql', Processor,
        'rdflib.plugins.sparql.processor', 'SPARQLProcessor')
rdflib.plugin.register('sparql', UpdateProcessor,
        'rdflib.plugins.sparql.processor', 'SPARQLUpdateProcessor')

# apps is a special folder where you can place your blueprints
PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_PATH, "apps"))

basestring = getattr(__builtins__, 'basestring', str)

# we create some comparison keys:
# increase probability that the rule will be near or at the top
top_compare_key = False, -100, [(-2, 0)]
# increase probability that the rule will be near or at the bottom 
bottom_compare_key = True, 100, [(2, 0)]

class NamespaceContainer:
    @property
    def prefixes(self):
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Namespace):
                result[key] = value
        return result

from rdfalchemy import *
from flask_ld.datastore import *

# Setup Flask-Security
class ExtendedRegisterForm(RegisterForm):
    identifier = TextField('Identifier', [validators.Required()])
    givenName = TextField('Given Name', [validators.Required()])
    familyName = TextField('Family Name', [validators.Required()])

# Form for full-text search
class SearchForm(Form):
    search_query = StringField('search_query', [validators.DataRequired()])

def to_json(result):
    return json.dumps([dict([(key, value.value if isinstance(value, Literal) else value) for key, value in x.items()]) for x in result.bindings])

class App(Empty):

    def configure_extensions(self):
        Empty.configure_extensions(self)
        self.celery = Celery(self.name, broker=self.config['CELERY_BROKER_URL'], beat=True)
        self.celery.conf.update(self.config)

        app = self

        def setup_task(service):
            service.app = app
            print service
            result = None
            if service.query_predicate == self.NS.graphene.globalChangeQuery:
                result = process_resource
            else:
                result = process_nanopub
            result.service = lambda : service
            return result

        @self.celery.task
        def process_resource(uri, service_name):
            service = self.config['inferencers'][service_name]
            print service, uri
            resource = app.get_resource(uri)
            service.process_graph(resource.graph)

        @self.celery.task
        def process_nanopub(nanopub_uri, service_name):
            service = self.config['inferencers'][service_name]
            print service, nanopub_uri
            nanopub = app.nanopub_manager.get(nanopub_uri)
            service.process_graph(nanopub)

        def setup_periodic_task(task):
            @self.celery.task
            def find_instances():
                print "Triggered task", task['name']
                for x, in app.db.query(task['service'].get_query()):
                    task['do'](x)
            
            @self.celery.task
            def do_task(uri):
                print "Running task", task['name'], 'on', uri
                resource = app.get_resource(uri)
                result = task['service'].process_graph(resource.graph)

            task['service'].app = app
            task['find_instances'] = find_instances
            task['do'] = do_task

            return task
            
        app.inference_tasks = []
        if 'inference_tasks' in self.config:
            app.inference_tasks = [setup_periodic_task(task) for task in self.config['inference_tasks']]

        for task in app.inference_tasks:
            if 'schedule' in task:
                #print "Scheduling task", task['name'], task['schedule']
                self.celery.add_periodic_task(
                    crontab(**task['schedule']),
                    task['find_instances'].s(),
                    name=task['name']
                )
            else:
                task['find_instances'].delay()
        
        @self.celery.task()
        def update(nanopub_uri):
            '''gets called whenever there is a change in the knowledge graph.
            Performs a breadth-first knowledge expansion of the current change.'''
            print "Updating on", nanopub_uri
            nanopub = app.nanopub_manager.get(nanopub_uri)
            if 'inferencers' in self.config:
                for name, service in self.config['inferencers'].items():
                    service.app = self
                    if service.query_predicate == self.NS.graphene.globalChangeQuery:
                        print "checking", name, service.get_query()
                        for uri, in app.db.query(service.get_query()):
                            print "invoking", name, uri
                            process_resource(uri, name)
                    if service.query_predicate == self.NS.graphene.updateChangeQuery:
                        print "checking", name, nanopub_uri, service.get_query()
                        if len(list(nanopub.query(service.get_query()))) > 0:
                            print "invoking", name, nanopub_uri
                            process_nanopub(nanopub_uri, name)

        def run_update(nanopub_uri):
            update.delay(nanopub_uri)
        self.nanopub_update_listener = run_update

    def configure_database(self):
        """
        Database configuration should be set here
        """
        self.NS = NamespaceContainer()
        self.NS.RDFS = rdflib.RDFS
        self.NS.RDF = rdflib.RDF
        self.NS.rdfs = rdflib.Namespace(rdflib.RDFS)
        self.NS.rdf = rdflib.Namespace(rdflib.RDF)
        self.NS.owl = rdflib.OWL
        self.NS.xsd   = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
        self.NS.dc    = rdflib.Namespace("http://purl.org/dc/terms/")
        self.NS.dcelements    = rdflib.Namespace("http://purl.org/dc/elements/1.1/")
        self.NS.auth  = rdflib.Namespace("http://vocab.rpi.edu/auth/")
        self.NS.foaf  = rdflib.Namespace("http://xmlns.com/foaf/0.1/")
        self.NS.prov  = rdflib.Namespace("http://www.w3.org/ns/prov#")
        self.NS.skos = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
        self.NS.cmo = rdflib.Namespace("http://purl.org/twc/ontologies/cmo.owl#")
        self.NS.sio = rdflib.Namespace("http://semanticscience.org/resource/")
        self.NS.sioc_types = rdflib.Namespace("http://rdfs.org/sioc/types#")
        self.NS.sioc = rdflib.Namespace("http://rdfs.org/sioc/ns#")
        self.NS.np = rdflib.Namespace("http://www.nanopub.org/nschema#")
        self.NS.graphene = rdflib.Namespace("http://vocab.rpi.edu/graphene/")
        self.NS.local = rdflib.Namespace(self.config['lod_prefix']+'/')
        self.NS.ov = rdflib.Namespace("http://open.vocab.org/terms/")


        self.admin_db = database.engine_from_config(self.config, "admin_")
        self.db = database.engine_from_config(self.config, "knowledge_")
        load_namespaces(self.db,locals())
        Resource.db = self.admin_db

        self.vocab = Graph()
        #print URIRef(self.config['vocab_file'])
        self.vocab.load(open(self.config['vocab_file']), format="turtle")

        self.role_api = ld.LocalResource(self.NS.prov.Role,"role", self.admin_db.store, self.vocab, self.config['lod_prefix'], RoleMixin)
        self.Role = self.role_api.alchemy

        self.user_api = ld.LocalResource(self.NS.prov.Agent,"user", self.admin_db.store, self.vocab, self.config['lod_prefix'], UserMixin)
        self.User = self.user_api.alchemy

        self.nanopub_api = ld.LocalResource(self.NS.np.Nanopublication,"pub", self.db.store, self.vocab, self.config['lod_prefix'], name="Graph")
        self.Nanopub = self.nanopub_api.alchemy

        self.classes = mapper(self.Role, self.User)
        self.datastore = RDFAlchemyUserDatastore(self.admin_db, self.classes, self.User, self.Role)
        self.security = Security(self, self.datastore,
                                 register_form=ExtendedRegisterForm)
        #self.mail = Mail(self)

    def weighted_route(self, *args, **kwargs):
        def decorator(view_func):
            compare_key = kwargs.pop('compare_key', None)
            # register view_func with route
            self.route(*args, **kwargs)(view_func)
    
            if compare_key is not None:
                rule = self.url_map._rules[-1]
                rule.match_compare_key = lambda: compare_key
    
            return view_func
        return decorator

    def map_entity(self, name):
        for importer in self.config['namespaces']:
            if importer.matches(name):
                new_name = importer.map(name)
                print 'Found mapped URI', new_name
                return new_name, importer
        return None, None

    def find_importer(self, name):
        for importer in self.config['namespaces']:
            if importer.resource_matches(name):
                return importer
        return None

        
    def get_resource(self, entity):
        mapped_name, importer = self.map_entity(entity)
    
        if mapped_name is not None:
            entity = mapped_name

        if importer is None:
            importer = self.find_importer(entity)

        if importer is not None:
            importer.load(entity, self.db, self.nanopub_manager)
            
        return self.get_entity(entity)

    def configure_template_filters(self):
        import urllib
        from markupsafe import Markup
    
        @self.template_filter('urlencode')
        def urlencode_filter(s):
            if type(s) == 'Markup':
                s = s.unescape()
            s = s.encode('utf8')
            s = urllib.quote_plus(s)
            return Markup(s)
    
    def configure_views(self):

        def sort_by(resources, property):
            return sorted(resources, key=lambda x: x.value(property))

        class InvitedAnonymousUser(AnonymousUserMixin):
            '''A user that has been referred via kikm references but does not have a user account.'''
            def __init__(self):
                self.roles = ImmutableList()

            def has_role(self, *args):
                """Returns `False`"""
                return False

            def is_active(self):
                return True

            @property
            def is_authenticated(self):
                return True

        def camel_case_split(identifier):
            matches = finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
            return [m.group(0) for m in matches]
            
        def get_label(resource):
            properties = [self.NS.dc.title, self.NS.RDFS.label, self.NS.skos.prefLabel, self.NS.foaf.name]
            for property in properties:
                label = resource.value(property)
                if label is not None:
                    return label
            for db in [self.db, self.admin_db]:
                for property in properties:
                    label = self.db.value(resource.identifier, property)
                    if label is not None:
                        return label
                    
                if label is None or len(label) < 2:
                    dbres = db.resource(resource.identifier)
                    name = [x.value for x in [dbres.value(self.NS.foaf.givenName),
                                              dbres.value(self.NS.foaf.familyName)] if x is not None]
                    if len(name) > 0:
                        label = ' '.join(name)
                        return label
            try:
                label = resource.graph.qname(resource.identifier).split(":")[1].replace("_"," ")
                return ' '.join(camel_case_split(label)).title()
            except Exception as e:
                print str(e), resource.identifier
                return str(resource.identifier)
            
        @self.before_request
        def load_forms():
            #g.search_form = SearchForm()
            g.ns = self.NS
            g.get_summary = get_summary
            g.get_label = get_label
            g.get_entity = self.get_entity
            g.rdflib = rdflib
            g.isinstance = isinstance

        @self.login_manager.user_loader
        def load_user(user_id):
            if user_id != None:
                return self.datastore.find_user(id=user_id)
            else:
                return None
            
        extensions = {
            "rdf": "application/rdf+xml",
            "json": "application/ld+json",
            "ttl": "text/turtle",
            "trig": "application/trig",
            "turtle": "text/turtle",
            "owl": "application/rdf+xml",
            "nq": "application/n-quads",
            "nt": "application/n-triples",
            "html": "text/html"
        }

        dataFormats = {
            "application/rdf+xml" : "xml",
            "application/ld+json" : 'json-ld',
            "text/turtle" : "turtle",
            "application/trig" : "trig",
            "application/n-quads" : "nquads",
            "application/n-triples" : "nt",
            None: "json-ld"
        }

        def get_graphs(graphs):
            query = 'select ?s ?p ?o ?g where {graph ?g {?s ?p ?o} } values ?g { %s }'
            query = query % ' '.join([graph.n3() for graph in graphs])
            #print query
            quads = self.db.store.query(query)
            result = Dataset()
            result.addN(quads)
            return result

        def get_entity(entity):
            try:
#                nanopubs = self.db.query('''select distinct ?s ?p ?o ?g where {
#            ?np np:hasAssertion?|np:hasProvenance?|np:hasPublicationInfo? ?g;
#                np:hasPublicationInfo ?pubinfo;
#                np:hasAssertion ?assertion;

#            {graph ?np { ?np sio:isAbout ?e.}}
#            UNION
#            {graph ?assertion { ?e ?p ?o.}}
            
#            graph ?g {?s ?p ?o.} 
#        }''',initBindings={'e':entity}, initNs={'np':self.NS.np, 'sio':self.NS.sio, 'dc':self.NS.dc, 'foaf':self.NS.foaf})
                nanopubs = self.db.query('''select distinct ?np where {
            ?np np:hasAssertion?|np:hasProvenance?|np:hasPublicationInfo? ?g;
                np:hasPublicationInfo ?pubinfo;
                np:hasAssertion ?assertion;

            {graph ?np { ?np sio:isAbout ?e.}}
            UNION
            {graph ?assertion { ?e ?p ?o.}}
        }''',initBindings={'e':entity}, initNs={'np':self.NS.np, 'sio':self.NS.sio, 'dc':self.NS.dc, 'foaf':self.NS.foaf})
                result = ConjunctiveGraph()
                for nanopub_uri, in nanopubs:
                    self.nanopub_manager.get(nanopub_uri, result)
#                result.addN(nanopubs)
            except Exception as e:
                print str(e), entity
                raise e
            #print result.serialize(format="trig")
            return result.resource(entity)

        self.get_entity = get_entity

        def get_summary(resource):
            summary_properties = [
                self.NS.skos.definition,
                self.NS.dc.abstract,
                self.NS.dc.description,
                self.NS.dc.summary,
                self.NS.RDFS.comment,
                self.NS.dcelements.description
            ]
            return resource.graph.preferredLabel(resource.identifier, default=[], labelProperties=summary_properties)

        self.get_summary = get_summary

        @self.route('/sparql', methods=['GET', 'POST'])
        @login_required
        def sparql_view():
            has_query = False
            for arg in request.args.keys():
                if arg.lower() == "update":
                    return "Update not allowed.", 403
                if arg.lower() == 'query':
                    has_query = True
            if request.method == 'GET' and not has_query:
                return redirect(url_for('sparql_form'))
            #print self.db.store.query_endpoint
            if request.method == 'GET':
                headers = {}
                headers.update(request.headers)
                del headers['Content-Length']
                req = requests.get(self.db.store.query_endpoint,
                                   headers = headers, params=request.args, stream = True)
            elif request.method == 'POST':
                if 'application/sparql-update' in request.headers['content-type']:
                    return "Update not allowed.", 403
                req = requests.post(self.db.store.query_endpoint, data=request.get_data(),
                                    headers = request.headers, params=request.args, stream = True)
            #print self.db.store.query_endpoint
            #print req.status_code
            response = Response(stream_with_context(req.iter_content()), content_type = req.headers['content-type'])
            #response.headers[con(req.headers)
            return response, req.status_code
        
        @self.route('/sparql.html')
        @login_required
        def sparql_form():
            template_args = dict(ns=self.NS,
                                 g=g,
                                 current_user=current_user,
                                 isinstance=isinstance,
                                 rdflib=rdflib,
                                 hasattr=hasattr,
                                 set=set)

            return render_template('sparql.html',endpoint="/sparql", **template_args)
        
            
        @self.route('/about.<format>')
        @self.route('/about')
        @self.weighted_route('/<path:name>.<format>', compare_key=bottom_compare_key)
        @self.weighted_route('/<path:name>', compare_key=bottom_compare_key)
        @self.route('/')
        @login_required
        def view(name=None, format=None, view=None):
            if format is not None:
                if format in extensions:
                    content_type = extensions[format]
                else:
                    name = '.'.join([name, format])
            if name is not None:
                entity = self.NS.local[name]
            elif 'uri' in request.args:
                entity = URIRef(request.args['uri'])
            else:
                entity = self.NS.local.Home

            resource = self.get_resource(entity)
            
            content_type = request.headers['Accept'] if 'Accept' in request.headers else '*/*'
            #print entity

            htmls = set(['application/xhtml','text/html'])
            if sadi.mimeparse.best_match(htmls, content_type) in htmls:
                return render_view(resource)
            else:
                fmt = dataFormats[sadi.mimeparse.best_match([mt for mt in dataFormats.keys() if mt is not None],content_type)]
                return resource.graph.serialize(format=fmt)


        views = {}
        def render_view(resource):
            template_args = dict(ns=self.NS,
                                 this=resource, g=g,
                                 current_user=current_user,
                                 isinstance=isinstance,
                                 get_entity=get_entity,
                                 get_summary=get_summary,
                                 rdflib=rdflib,
                                 hasattr=hasattr,
                                 set=set)
            view = None
            if 'view' in request.args:
                view = request.args['view']
            # 'view' is the default view
            content = resource.value(self.NS.sioc.content)
            #if (view == 'view' or view is None) and content is not None:
            #    if content is not None:
            #        return render_template('content_view.html',content=content, **template_args)
            value = resource.value(self.NS.prov.value)
            if value is not None and view is None:
                headers = {}
                headers['ContentType'] = 'text/plain'
                content_type = resource.value(self.NS.ov.hasContentType)
                if content_type is not None:
                    headers['ContentType'] = content_type
                if value.datatype == XSD.base64Binary:
                    return base64.b64decode(value.value), 200, headers
                if value.datatype == XSD.hexBinary:
                    return binascii.unhexlify(value.value), 200, headers
                return value.value, 200, headers

            if view is None:
                view = 'view'

            if 'as' in request.args:
                types = [URIRef(request.args['as']), 0]
            else:
                types = list([(x.identifier, 0) for x in resource[RDF.type]])
            #if len(types) == 0:
            types.append([self.NS.RDFS.Resource, 100])
            #print view, resource.identifier, types
            type_string = ' '.join(["(%s %d '%s')" % (x.n3(), i, view) for x, i in types])
            view_query = '''select ?id ?view (count(?mid)+?priority as ?rank) ?class ?c where {
    values (?c ?priority ?id) { %s }
    ?c rdfs:subClassOf* ?mid.
    ?mid rdfs:subClassOf* ?class.
    ?class ?viewProperty ?view.
    ?viewProperty rdfs:subPropertyOf* graphene:hasView.
    ?viewProperty dc:identifier ?id.
} group by ?c ?class order by ?rank
''' % type_string

            #print view_query
            views = list(self.vocab.query(view_query, initNs=dict(graphene=self.NS.graphene, dc=self.NS.dc)))
            #print '\n'.join([str(x.asdict()) for x in views])
            if len(views) == 0:
                abort(404)

            # default view (list of nanopubs)
            # if available, replace with class view
            # if available, replace with instance view
            return render_template(views[0]['view'].value, **template_args)

        self.api = ld.LinkedDataApi(self, "", self.db.store, "")

        self.admin = Admin(self, name="graphene", template_mode='bootstrap3')
        self.admin.add_view(ld.ModelView(self.nanopub_api, default_sort=RDFS.label))
        self.admin.add_view(ld.ModelView(self.role_api, default_sort=RDFS.label))
        self.admin.add_view(ld.ModelView(self.user_api, default_sort=foaf.familyName))

        app = self

        self.nanopub_manager = NanopublicationManager(app.db.store, app.config['nanopub_archive_path'],
                                                      Namespace('%s/pub/'%(app.config['lod_prefix'])),
                                                      update_listener=self.nanopub_update_listener)
        class NanopublicationResource(ld.LinkedDataResource):
            decorators = [login_required]

            def __init__(self):
                self.local_resource = app.nanopub_api

            def _can_edit(self, uri):
                if current_user.has_role('Publisher') or current_user.has_role('Editor')  or current_user.has_role('Admin'):
                    return True
                if app.db.query('''ask {
                    ?nanopub np:hasAssertion ?assertion; np:hasPublicationInfo ?info.
                    graph ?info { ?assertion dc:contributor ?user. }
                    }''', initBindings=dict(nanopub=uri, user=current_user.resUri), initNs=dict(np=app.NS.np, dc=app.NS.dc)):
                    #print "Is owner."
                    return True
                return False

            def _get_uri(self, ident):
                return URIRef('%s/pub/%s'%(app.config['lod_prefix'], ident))

            def get(self, ident):
                ident = ident.split("_")[0]
                uri = self._get_uri(ident)
                try:
                    result = app.nanopub_manager.get(uri)
                except IOError:
                    return 'Resource not found', 404
                return result

            def delete(self, ident):
                uri = self._get_uri(ident)
                if not self._can_edit(uri):
                    return '<h1>Not Authorized</h1>', 401
                app.nanopub_manager.retire(uri)
                #self.local_resource.delete(uri)
                return '', 204

            def _get_graph(self):
                inputGraph = ConjunctiveGraph()
                contentType = request.headers['Content-Type']
                sadi.deserialize(inputGraph, request.data, contentType)
                return inputGraph
            
            def put(self, ident):
                nanopub_uri = self._get_uri(ident)
                inputGraph = self._get_graph()
                old_nanopub = self._prep_nanopub(nanopub_uri, inputGraph)
                for nanopub in app.nanopub_manager.prepare(inputGraph):
                    modified = Literal(datetime.utcnow())
                    nanopub.pubinfo.add((nanopub.assertion.identifier, app.NS.prov.wasRevisionOf, old_nanopub.assertion.identifier))
                    nanopub.pubinfo.add((old_nanopub.assertion.identifier, app.NS.prov.invalidatedAtTime, modified))
                    nanopub.pubinfo.add((nanopub.assertion.identifier, app.NS.dc.modified, modified))
                    app.nanopub_manager.retire(nanopub_uri)
                    app.nanopub_manager.publish(nanopub)

            def _prep_nanopub(self, nanopub_uri, graph):
                nanopub = Nanopublication(store=graph.store, identifier=nanopub_uri)
                about = nanopub.nanopub_resource.value(app.NS.sio.isAbout)
                #print nanopub.assertion_resource.identifier, about
                self._prep_graph(nanopub.assertion_resource, about.identifier)
                self._prep_graph(nanopub.pubinfo_resource, nanopub.assertion_resource.identifier)
                self._prep_graph(nanopub.provenance_resource, nanopub.assertion_resource.identifier)
                nanopub.pubinfo.add((nanopub.assertion.identifier, app.NS.dc.contributor, current_user.resUri))
                return nanopub
            
            def post(self, ident=None):
                if ident is not None:
                    return self.put(ident)
                inputGraph = self._get_graph()
                for nanopub_uri in inputGraph.subjects(rdflib.RDF.type, app.NS.np.Nanopublication):
                    nanopub = self._prep_nanopub(nanopub_uri, inputGraph)
                    nanopub.pubinfo.add((nanopub.assertion.identifier, app.NS.dc.created, Literal(datetime.utcnow())))
                for nanopub in app.nanopub_manager.prepare(inputGraph):
                    app.nanopub_manager.publish(nanopub)

                return '', 201


            def _prep_graph(self, resource, about = None):
                #print '_prep_graph', resource.identifier, about
                content_type = resource.value(app.NS.ov.hasContentType)
                if content_type is not None:
                    content_type = content_type.value
                #print 'graph content type', resource.identifier, content_type
                #print resource.graph.serialize(format="nquads")
                g = Graph(store=resource.graph.store,identifier=resource.identifier)
                text = resource.value(app.NS.prov.value)
                if content_type is not None and text is not None:
                    #print 'Content type:', content_type, resource.identifier
                    html = None
                    if content_type in ["text/html", "application/xhtml+xml"]:
                        html = Literal(text.value, datatype=RDF.HTML)
                    if content_type == 'text/markdown':
                        #print "Aha, markdown!"
                        #print text.value
                        html = markdown.markdown(text.value, extensions=['rdfa'])
                        attributes = ['vocab="%s"' % app.NS.local,
                                      'base="%s"'% app.NS.local,
                                      'prefix="%s"' % ' '.join(['%s: %s'% x for x in app.NS.prefixes.items()])]
                        if about is not None:
                            attributes.append('resource="%s"' % about)
                        html = '<div %s>%s</div>' % (' '.join(attributes), html)
                        html = Literal(html, datatype=RDF.HTML)
                        text = html
                        content_type = "text/html"
                    #print resource.identifier, content_type
                    if html is not None:
                        resource.add(app.NS.sioc.content, html)
                        try:
                            g.parse(data=text, format='rdfa')
                        except:
                            pass
                    else:
                        #print "Deserializing", g.identifier, 'as', content_type
                        #print dataFormats
                        if content_type in dataFormats:
                            g.parse(data=text, format=dataFormats[content_type])
                            #print len(g)
                        else:
                            print "not attempting to deserialize."
#                            try:
#                                sadi.deserialize(g, text, content_type)
#                            except:
#                                pass
                #print Graph(store=resource.graph.store).serialize(format="trig")
        self.api.add_resource(NanopublicationResource, '/pub', '/pub/<ident>')


def config_str_to_obj(cfg):
    if isinstance(cfg, basestring):
        module = __import__('config', fromlist=[cfg])
        return getattr(module, cfg)
    return cfg


def app_factory(config, app_name, blueprints=None):
    # you can use Empty directly if you wish
    app = App(app_name)
    config = config_str_to_obj(config)
    #print dir(config)
    app.configure(config)
    if blueprints:
        app.add_blueprint_list(blueprints)
    app.setup()

    return app


def heroku():
    from config import Config, project_name
    # setup app through APP_CONFIG envvar
    return app_factory(Config, project_name)
