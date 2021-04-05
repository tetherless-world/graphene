
import { literal, namedNode } from '@rdfjs/data-model'
import { fromRdf } from 'rdf-literal'

import { listNanopubs, getLocalNanopub, describeNanopub, postNewNanopub, deleteNanopub, lodPrefix } from 'utilities/nanopub'
import { querySparql } from 'utilities/sparql'

const defaultQuery = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?c (MIN(?class) AS ?class) (COUNT(?x) AS ?count)
WHERE {
    ?x a ?c.
    ?c rdfs:label ?class.
}
GROUP BY ?c
ORDER BY DESC(?count)
`.trim()

const defaultSpec = {
  "$schema": "https://vega.github.io/schema/vega-lite/v4.json",
  "mark": "bar",
  "encoding": {
    "x": {
      "field": "count",
      "type": "quantitative"
    },
    "y": {
      "field": "class",
      "type": "ordinal"
    }
  }
}

const defaultChart = {
  uri: null,
  baseSpec: defaultSpec,
  query: defaultQuery,
  title: 'Example Bar Chart',
  description: 'An example chart that looks up the frequency for each class in the knowledge graph.',
  depiction: null,
}

const chartType = 'http://semanticscience.org/resource/Chart'

const foafDepictionUri = 'http://xmlns.com/foaf/0.1/depiction'
const hasContentUri = 'http://vocab.rpi.edu/whyis/hasContent'

const chartFieldUris = {
  baseSpec: 'http://semanticscience.org/resource/hasValue',
  query: 'http://schema.org/query',
  title: 'http://purl.org/dc/terms/title',
  description: 'http://purl.org/dc/terms/description',
}

const chartPrefix = 'viz'
const chartIdLen = 16

function generateChartId () {
  const intArr = new Uint8Array(chartIdLen / 2)
  window.crypto.getRandomValues(intArr)
  const chartId = Array.from(intArr, (dec) => ('0' + dec.toString(16)).substr(-2)).join('')

  return `${lodPrefix}/${chartPrefix}/${chartId}`
}

function buildChartLd (chart) {
  chart = Object.assign({}, chart)
  chart.baseSpec = JSON.stringify(chart.baseSpec)
  const chartLd =  {
    '@id': chart.uri,
    '@type': [chartType],
    [foafDepictionUri]: {
      '@id': `${chart.uri}_depiction`,
      [hasContentUri]: chart.depiction
    }
  }
  Object.entries(chart)
    .filter(([field, value]) => chartFieldUris[field])
    .forEach(([field, value]) => chartLd[chartFieldUris[field]] = [{ '@value': value }])
  return chartLd
}

function extractChart (chartLd) {
  const chart = {uri: chartLd['@id']}

  if (chartLd[foafDepictionUri]) {
    chart.depiction = chartLd[foafDepictionUri][0]['@id']
  }

  Object.entries(chartFieldUris)
    .forEach(([field, uri]) => {
      let value = ""
      if (uri in chartLd) {
        value = chartLd[uri][0]['@value']
      }
      chart[field] = value
    })
  chart.baseSpec = JSON.parse(chart.baseSpec)
  return chart
}

function getDefaultChart () {
  return Object.assign({}, defaultChart)
}

/**
 * Copies the given chart except for the id field, which is generated from scratch
 * also the depiction is removed
 */
function copyChart(sourceChart) {
  // Shallow copy is OK for the current chart structure
  const newChart = Object.assign({}, sourceChart)
  newChart.uri = generateChartId()
  delete newChart.depiction
  return newChart
}

function loadChartFromNanopub(nanopubUri, chartUri) {
  return describeNanopub(nanopubUri)
    .then((describeData) => {
      const assertion_id = `${nanopubUri}_assertion`
      for (let graph of describeData) {
        if (graph['@id'] === assertion_id) {
          for (let resource of graph['@graph']) {
            // Use the chart URI, if provided, to identify the chart.
            // Otherwise, just grab the first chart found.
            let chartMatch
            if (chartUri) {
              chartMatch = resource['@id'] === chartUri
            } else {
              const typeArray = resource['@type']
              chartMatch = typeArray && (typeArray.indexOf(chartType) >= 0)
            }
            if (chartMatch) {
              return extractChart(resource)
            }
          }
        }
      }
    })
}

function loadChart (chartUri) {
  return listNanopubs(chartUri)
    .then(nanopubs => {
      if (nanopubs.length > 0) {
        const nanopubUri = nanopubs[0].np
        return loadChartFromNanopub(nanopubUri, chartUri)
      }
    })
}

function saveChart (chart) {
  let deletePromise = Promise.resolve()
  if (chart.uri) {
    deletePromise = deleteChart(chart.uri)
  } else {
    chart.uri = generateChartId()
  }
  const chartLd = buildChartLd(chart)
  return deletePromise
    .then(() => postNewNanopub(chartLd))
}

function deleteChart (chartUri) {
  console.log('Deleting chart', chartUri)
  return listNanopubs(chartUri)
    .then(nanopubs => Promise.all(nanopubs.map(nanopub => deleteNanopub(nanopub.np))))
}

const chartQuery = `
  PREFIX dcterms: <http://purl.org/dc/terms/>
  PREFIX schema: <http://schema.org/>
  PREFIX sio: <http://semanticscience.org/resource/>
  PREFIX owl: <http://www.w3.org/2002/07/owl#>
  PREFIX foaf: <http://xmlns.com/foaf/0.1/>
  SELECT DISTINCT ?uri ?title ?description ?query ?baseSpec ?depiction
  WHERE {
    ?uri a sio:Chart ;
         dcterms:title ?title ;
         dcterms:description ?description ;
         schema:query ?query ;
         sio:hasValue ?baseSpec ;
         foaf:depiction ?depiction .
  }
  `

function getCharts () {
  return querySparql(chartQuery)
    .then(data =>
      data.results.bindings.map((chartResult) => {
        const chart = {}
        Object.entries(chartResult)
          .forEach(([field, value]) => chart[field] = value.value)
        chart.baseSpec = JSON.parse(chart.baseSpec)
        return chart
      })
    )

}

function transformSparqlData (sparqlResults) {
  const data = []
  if (sparqlResults) {
    for (const row of sparqlResults.results.bindings) {
      const resultData = {}
      data.push(resultData)
      Object.entries(row).forEach(([field, result, t]) => {
        let value = result.value
        if (result.type === 'literal' && result.datatype) {
          value = fromRdf(literal(value, namedNode(result.datatype)))
        }
        resultData[field] = value
      })
    }
  }
  return data
}

function buildSparqlSpec (baseSpec, sparqlResults) {
  if (!baseSpec) {
    return null
  }
  const spec = Object.assign({}, baseSpec)
  spec.data = { values: transformSparqlData(sparqlResults) }
  return spec
}

export { getDefaultChart, loadChart, saveChart, copyChart, getCharts, buildSparqlSpec, transformSparqlData}
