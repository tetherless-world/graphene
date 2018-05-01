import rdflib
import filters

prefixes = dict(
    skos = rdflib.URIRef("http://www.w3.org/2004/02/skos/core#"),
    foaf = rdflib.URIRef("http://xmlns.com/foaf/0.1/"),
    bds = rdflib.URIRef("http://www.bigdata.com/rdf/search#"),
    dc = rdflib.URIRef("http://purl.org/dc/terms/")
        )

def resolve(graph, g, term, context=None):
    context_query = ''
    if context is not None:
        context_query = """
  optional {
    ?node ?p ?context.
    ?context bds:search '''%s''';
         bds:matchAllTerms "false";
		 bds:relevance ?cr ;
         bds:minRelevance 0.4.
  }
""" % context
        
    query = """
select distinct
?node
?label
#(group_concat(distinct ?type; separator="||") as ?types)
(coalesce(?relevance+?cr, ?relevance) as ?score)
where {
  ?node dc:title|rdfs:label|skos:prefLabel|skos:altLabel|foaf:name ?label.
  ?label bds:search '''%s''';
         bds:matchAllTerms "false";
		 bds:relevance ?relevance .
  
  ?node dc:title|rdfs:label|skos:prefLabel|skos:altLabel|foaf:name ?label.
  
#  optional {
#    ?node rdf:type/rdfs:subClassOf* ?type.
#  }

  %s
  
  filter not exists {
    [] ?node [].
  }
  filter not exists {
    ?node a <http://semanticscience.org/resource/Term>
  }
  filter not exists {
    ?node a <http://www.nanopub.org/nschema#Nanopublication>
  }
  filter not exists {
    ?node a <http://www.nanopub.org/nschema#Assertion>
  }
  filter not exists {
    ?node a <http://www.nanopub.org/nschema#Provenance>
  }
  filter not exists {
    ?node a owl:AnnotationProperty.
  }
  filter not exists {
    ?node a owl:ObjectProperty.
  }
  filter not exists {
    ?node a owl:DatatypeProperty.
  }
  filter not exists {
    ?node a <http://www.nanopub.org/nschema#PublicationInfo>
  }
} group by ?node ?label ?score ?cr ?relevance order by desc(?score) limit 10""" % (term, context_query)
    print query
    results = []
    for hit in graph.query(query, initNs=prefixes):
        result = hit.asdict()
        g.labelize(result,'node','preflabel')
        #result['types'] = [g.labelize({'uri':x},'uri','label') for x in result['types'].split('||')]
        results.append(result)
    return results

latest_query = '''select distinct 
?about 
(max(?created) as ?updated)
(group_concat(distinct ?type; separator="||") as ?types)
where {
    hint:Query hint:optimizer "Runtime" .                                                                                              graph ?np {
    ?np 
        np:hasPublicationInfo ?pubinfo;
        np:hasAssertion ?assertion.
  }
  graph ?pubinfo {
      ?assertion dc:created|dc:modified ?created.
  }
    {
      graph ?np { 
        ?np sio:isAbout ?about.
      }
    }
  
    filter not exists {
      [] ?about [].
    }
    optional {
      ?about a ?type.
    }
    
} group by ?about order by desc (?updated)
LIMIT 20
'''

def latest(graph, g):
    results = []
    entities = {}
    for row in graph.query(latest_query, initNs=g.ns.prefixes):
        entry = row.asdict()
        if entry['about'] not in entities:
            entities[entry['about']] = entry
            results.append(entry)
        entity = g.get_resource(rdflib.URIRef(entry['about']), retrieve=False)
        print("entity is:", entity)
        if 'label' not in entities[entry['about']]:
            entry['label'] = g.get_label(entity)
        if 'description' not in entities[entry['about']]:
            d = [y for x,y in g.get_summary(entity)]
            if len(d) > 0:
                entry['description'] = d[0]
        if entities[entry['about']] == entry or 'types' not in entities[entry['about']] or len(entities[entry['about']]['types']) == 0:
            entities[entry['about']]['types'] = [g.labelize(dict(uri=x),'uri','label')
                                                 for x in entry['types'].split('||') if len(x) > 0]
    return results
                                


def search(graph, args, g):
  finalResults = []
  results = []
  typeList = []
  labelsList = []
  print('query in search.py: ', args['query'])  
  query = args['query']
  print('g is:', g)
   #check for page arg
  print("args['page'] is ", args['page'])
  #make sure paging works if args['page'] not included
  try:
    if int(args['page'])  == 0:
      page = 1
    else:
      page = int(args['page'])
  except:
    page = 1
  print('page is:', page)

   #create number of results wanted at a time and use with page for pagination
  limit = 10
  
  #this is used for offset in sparql query
  pageOffset = (page - 1) * limit

  search_query = '''PREFIX bds: <http://www.bigdata.com/rdf/search#>

  SELECT ?sub (sample(?pred) as ?pred) (sample(?obj) as ?obj) (max(?score) as ?score) 
    (group_concat(distinct ?type; separator="||") as ?types)
  WHERE {
      ?obj bds:search "%s" .
      ?obj bds:relevance ?score .  		
      ?sub ?pred ?obj .
  OPTIONAL { 
      ?sub rdf:type ?type.
    }
  } group by ?sub having (max(?score) = ?score) ORDER BY DESC(?score)
    LIMIT %d
    OFFSET %d''' % (query, limit, pageOffset)
  #query and gather each row for result JSON
  for row in graph.query(search_query, initNs=g.ns.prefixes):
    result = row.asdict()
    g.labelize( result, "sub" )
    results.append( result )
  
  #add loop to split up the types into 
  for item in results:
    if item['types'] is not None:
      for type in item['types'].split('||'):
        #leverage labelize for each link after splitting
        labelsList.append( g.labelize( {"uri": type}, 'uri' ) )
        typeList.append(type)
    item['typeLabels'] = labelsList
    item['type'] = typeList
    # print("typeList is:", typeList)
    typeList = [] #reset typeList for next item
  
  #add page for pagination
  finalResults.append({'data': results})
  finalResults[0]['page'] = page 

  #add in count query
  countQuery = '''PREFIX bds: <http://www.bigdata.com/rdf/search#>

  SELECT  
	(COUNT(DISTINCT ?sub) as ?count)
	
  WHERE {
      ?obj bds:search "%s" .  		
      ?sub ?pred ?obj .
  OPTIONAL { 
      ?sub rdf:type ?type.
    }
  } ''' % query
  print('countQuery is:', countQuery)
  countResults = []
  countItems = 0
  countList = []
  
  for row in graph.query(countQuery, initNs=g.ns.prefixes):
    countResult = row.asdict()
    countResults.append( countResult )
  print('countResults is:',countResults)

  #count for while loop
  count = int(countResults[0]['count'])
  #logic for paging!
  if (count > pageOffset and page > 0):
    count = count - pageOffset
  while (count > 0):
    countList.append( count )
    count = count - 1
  print('countList is:', countList)

  #add in more to JSON
  finalResults[0]['Total Results'] = int(countResults[0]['count'])#total number without paging
  finalResults[0]['count'] =  len(countList)
  finalResults[0]['countList'] = countList
  finalResults[0]['query'] = query
  finalResults[0]['limit'] = limit

  return finalResults



