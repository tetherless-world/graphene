from __future__ import print_function
from builtins import str
import sadi
import rdflib
import setlr
from datetime import datetime
from nanopub import Nanopublication
from datastore import create_id
import flask
from flask import render_template
from flask import render_template_string
import logging

import sys, traceback

import database

import tempfile

from depot.io.interfaces import StoredFile

whyis = rdflib.Namespace('http://vocab.rpi.edu/whyis/')
whyis = rdflib.Namespace('http://vocab.rpi.edu/whyis/')
np = rdflib.Namespace("http://www.nanopub.org/nschema#")
prov = rdflib.Namespace("http://www.w3.org/ns/prov#")
dc = rdflib.Namespace("http://purl.org/dc/terms/")
sio = rdflib.Namespace("http://semanticscience.org/resource/")
setl = rdflib.Namespace("http://purl.org/twc/vocab/setl/")
pv = rdflib.Namespace("http://purl.org/net/provenance/ns#")
skos = rdflib.Namespace("http://www.w3.org/2008/05/skos#")

setlr_handlers_added = False


class SETLr(UpdateChangeService):
    activity_class = setl.SemanticETL

    def __init__(self, depth=-1, predicates=[None]):
        self.depth = depth
        self.predicates = predicates

        global setlr_handlers_added
        if not setlr_handlers_added:
            def _whyis_content_handler(location):
                resource = self.app.get_resource(location)
                fileid = resource.value(self.app.NS.whyis.hasFileID)
                if fileid is not None:
                    return self.app.file_depot.get(fileid)

            setlr.content_handlers.insert(0, _whyis_content_handler)
            setlr_handlers_added = True

    def getInputClass(self):
        return setl.SemanticETLScript

    def getOutputClass(self):
        return whyis.ProcessedSemanticETLScript

    def get_query(self):
        return '''select distinct ?resource where { ?resource a %s.}''' % self.getInputClass().n3()

    def explain(self, nanopub, i, o):
        np_assertions = list(i.graph.subjects(rdflib.RDF.type, np.Assertion)) + [nanopub.assertion.identifier]
        activity = nanopub.provenance.resource(rdflib.BNode())
        activity.add(rdflib.RDF.type, i.identifier)
        nanopub.provenance.add((nanopub.assertion.identifier, prov.wasGeneratedBy, activity.identifier))
        for assertion in np_assertions:
            nanopub.provenance.add((activity.identifier, prov.used, assertion))
            nanopub.provenance.add((nanopub.assertion.identifier, prov.wasDerivedFrom, assertion))
            nanopub.pubinfo.add((nanopub.assertion.identifier, prov.wasAttributedTo, i.identifier))
            nanopub.pubinfo.add((nanopub.assertion.identifier, prov.wasAttributedTo, i.identifier))

    def process(self, i, o):
        query_store = self.app.db.store
        if hasattr(query_store, 'endpoint'):
            query_store = database.create_query_store(self.app.db.store)
        db_graph = rdflib.ConjunctiveGraph(store=query_store)
        db_graph.NS = self.app.NS
        setlr.actions[whyis.sparql] = db_graph
        setlr.actions[whyis.NanopublicationManager] = self.app.nanopub_manager
        setlr.actions[whyis.Nanopublication] = self.app.nanopub_manager.new
        setl_graph = i.graph
        #        setlr.run_samples = True
        resources = setlr._setl(setl_graph)
        # retire old copies
        old_np_map = {}
        to_retire = []
        for new_np, assertion, orig in self.app.db.query('''select distinct ?np ?assertion ?original_uri where {
    ?np np:hasAssertion ?assertion.
    ?assertion a np:Assertion;
        prov:wasGeneratedBy/a ?setl;
        prov:wasQuotedFrom ?original_uri.
}''', initBindings=dict(setl=i.identifier), initNs=dict(prov=prov, np=np)):
            old_np_map[orig] = assertion
            to_retire.append(new_np)
            if len(to_retire) > 100:
                self.app.nanopub_manager.retire(*to_retire)
                to_retire = []
        self.app.nanopub_manager.retire(*to_retire)
        # print resources
        for output_graph in setl_graph.subjects(prov.wasGeneratedBy, i.identifier):
            if setl_graph.resource(output_graph)[rdflib.RDF.type:whyis.NanopublicationCollection]:
                self.app.nanopub_manager.publish(resources[output_graph])
            else:
                out = resources[output_graph]
                out_conjunctive = rdflib.ConjunctiveGraph(store=out.store, identifier=output_graph)
                # print "Generated graph", out.identifier, len(out), len(out_conjunctive)
                nanopub_prepare_graph = rdflib.ConjunctiveGraph(store="Sleepycat")
                nanopub_prepare_graph_tempdir = tempfile.mkdtemp()
                nanopub_prepare_graph.store.open(nanopub_prepare_graph_tempdir, True)

                mappings = {}

                to_publish = []
                triples = 0
                for new_np in self.app.nanopub_manager.prepare(out_conjunctive, mappings=mappings,
                                                               store=nanopub_prepare_graph.store):
                    self.explain(new_np, i, o)
                    orig = [orig for orig, new in list(mappings.items()) if new == new_np.assertion.identifier]
                    if len(orig) == 0:
                        continue
                    orig = orig[0]
                    print(orig)
                    if isinstance(orig, rdflib.URIRef):
                        new_np.pubinfo.add((new_np.assertion.identifier, prov.wasQuotedFrom, orig))
                        if orig in old_np_map:
                            new_np.pubinfo.add((new_np.assertion.identifier, prov.wasRevisionOf, old_np_map[orig]))
                    print("Publishing %s with %s assertions." % (new_np.identifier, len(new_np.assertion)))
                    to_publish.append(new_np)

                # triples += len(new_np)
                # if triples > 10000:
                self.app.nanopub_manager.publish(*to_publish)
                nanopub_prepare_graph.store.close()
            print("Published")
        for resource, obj in list(resources.items()):
            if hasattr(i, 'close'):
                print("Closing", resource)
                try:
                    i.close()
                except:
                    pass


class Deductor(UpdateChangeService):
    def __init__(self, where, construct, explanation, resource="?resource", prefixes=None):  # prefixes should be
        if resource is not None:
            self.resource = resource
        self.prefixes = {}
        if prefixes is not None:
            self.prefixes = prefixes
        self.where = where
        self.construct = construct
        self.explanation = explanation

    def getInputClass(self):
        return pv.File  # input and output class should be customized for the specific inference

    def getOutputClass(self):
        return setl.SETLedFile

    def get_query(self):
        self.app.db.store.nsBindings = {}
        return '''SELECT DISTINCT %s WHERE {\n%s \nFILTER NOT EXISTS {\n%s\n\t}\n}''' % (
        self.resource, self.where, self.construct)

    def get_context(self, i):
        context = {}
        context_vars = self.app.db.query('''SELECT DISTINCT * WHERE {\n%s \nFILTER(regex(str(%s), "^(%s)")) . }''' % (
        self.where, self.resource, i.identifier), initNs=self.prefixes)
        # print(context_vars)
        for key in list(context_vars.json["results"]["bindings"][0].keys()):
            context[key] = context_vars.json["results"]["bindings"][0][key]["value"]
        return context

    def process(self, i, o):
        npub = Nanopublication(store=o.graph.store)
        triples = self.app.db.query(
            '''CONSTRUCT {\n%s\n} WHERE {\n%s \nFILTER NOT EXISTS {\n%s\n\t}\nFILTER (regex(str(%s), "^(%s)")) .\n}''' % (
            self.construct, self.where, self.construct, self.resource, i.identifier), initNs=self.prefixes)
        for s, p, o, c in triples:
            print("Deductor Adding ", s, p, o)
            npub.assertion.add((s, p, o))
        npub.provenance.add((npub.assertion.identifier, prov.value,
                             rdflib.Literal(flask.render_template_string(self.explanation, **self.get_context(i)))))

    def __str__(self):
        return "Deductor Instance: " + str(self.__dict__)
