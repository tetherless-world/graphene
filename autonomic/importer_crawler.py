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


class ImporterCrawler(UpdateChangeService):
    activity_class = whyis.ImporterGraphCrawl

    def getInputClass(self):
        return whyis.ImporterResource

    def getOutputClass(self):
        return whyis.ImportedResource

    _query = None

    def get_query(self):
        if self._query is None:
            prefixes = [x.detect_url for x in self.app.config['namespaces']]
            self._query = '''select distinct ?resource where {
  graph ?assertion {
    {?s ?p ?resource . } union {?resource ?p ?o}
  }
  FILTER (regex(str(?resource), "^(%s)")) .
  filter not exists {
    ?assertion prov:wasGeneratedBy [ a whyis:KnowledgeImport].
  }
} ''' % '|'.join(prefixes)
            print(self._query)

        return self._query

    def process(self, i, o):
        node = self.app.run_importer(i.identifier)
