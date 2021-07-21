import { literal, namedNode } from '@rdfjs/data-model'
import { fromRdf } from 'rdf-literal'
import { querySparql } from "../../../utilities/sparql";
import loadSparqlTemplatesQuery from './load-sparql-templates.rq'
import {RDF, RDFS, SCHEMA} from '../../../utilities/common-namespaces'

const SP = 'http://spinrdf.org/sp'
const SPIN = `${SP}in#`

const templateType = 'http://vocab.rpi.edu/whyis/SparqlTemplate'
const typePred = RDF + 'type'

export async function loadSparqlTemplates() {
  const queryResponse = await querySparql(loadSparqlTemplatesQuery, {accept: "application/rdf+json"})

  // Generate map data structure of {subject: {predicate: (set of objects) }}
  // TODO: this step could have been simplified by requesting json-ld  - "Accept: application/ld+json'"
  const subjectMap = {}
  const templateUris = []
  queryResponse.results.bindings.forEach(b => {
    const subject = b.subject.value
    const predicate = b.predicate.value
    let object = b.object.value
    if (b.object.type === "literal" && b.object.datatype) {
      object = fromRdf(literal(object, namedNode(b.object.datatype)))
    }

    // Identify template uris
    if (predicate === typePred && object === templateType) {
      templateUris.push(subject)
    }

    let predicateMap = subjectMap[subject]
    if (!predicateMap) {
      predicateMap = {}
      subjectMap[subject] = predicateMap
    }
    let objectSet = predicateMap[predicate]
    if (!objectSet) {
      objectSet = new Set()
      predicateMap[predicate] = objectSet
    }
    objectSet.add(object)
  })

  // Use a recursive function to form objects from triples
  const resolvedTemplates = templateUris.map((templateUri) => resolveUri(templateUri))

  // Transform objects so that they are usable in the query templates page
  const transformedTemplates = resolvedTemplates.map(transformTemplate)
  transformedTemplates.sort((a, b) => a.id > b.id ? 1 : -1)
  return transformedTemplates

  function resolveUri(uri, visited) {
    visited = visited || new Set()
    if (visited.has(uri) || !subjectMap.hasOwnProperty(uri)) {
      return uri
    }
    visited.add(uri)
    const predMap = subjectMap[uri]
    const obj = {uri}
    Object.entries(predMap)
      .forEach(([pred, values]) => {
        const resolvedVals = [...values].map(vUri => resolveUri(vUri, visited))
        obj[pred] = resolvedVals
      })
    return obj
  }
}

/**
 * Identifies segments of display text as being variables or text
 */
export const TextSegmentType = Object.freeze({
  VAR: "var",
  TEXT: "text"
});

/**
 * Enumeration of types of query parameter option values.
 */
export const OptValueType = Object.freeze({
  ANY: "any",
  LITERAL: "literal",
  IDENTIFIER: "identifier"
})

/**
 * Transforms rdf proto-template into a usable template
 */
function transformTemplate(template) {
  const displayText = template[`${SPIN}labelTemplate`][0]
  return {
    id: template.uri,
    display: displayText,
    displaySegments: parseDisplayText(displayText),
    SPARQL: template[`${SP}text`][0],
    options: transformTemplateParams(template[`${SPIN}constraint`])
  }
}

function transformTemplateParams(params) {
  return Object.fromEntries(
    params.map(param => [
      param[`${SP}varName`][0],
      transformParamOpts(param[`${SCHEMA}option`])
    ])
  )
}

function transformParamOpts(opts) {
  return Object.fromEntries(
    opts.map(opt => [
        opt[`${RDFS}label`][0],
        getOptValue(opt),
        opt[`${SCHEMA}position`][0],
    ])
    .sort((e1, e2) => (e1[2] > e2[2]) ? 1: -1)
  )
}

function getOptValue(opt) {
  let value = {
    type: OptValueType.ANY
  }
  if (opt[`${SCHEMA}value`]) {
    const rawVal = opt[`${SCHEMA}value`]
    value = {
      type: OptValueType.LITERAL,
      value: opt[`${SCHEMA}value`][0]
    }
  } else if (opt[`${SCHEMA}identifier`]) {
    value = {
      type: OptValueType.IDENTIFIER,
      value: opt[`${SCHEMA}identifier`][0]
    }
  }
  return value
}

// Matches query variables in display text
const qVarRegex = /{\?([^}]+)}/g
// Matches query variables or the text between query variables
const segmentRegex = new RegExp(`${qVarRegex.source}|[^{]+`, "g")

function parseDisplayText(displayText) {
  return displayText.match(segmentRegex).map(token => {
    let displaySegment;
    const match = qVarRegex.exec(token)
    if (match) {
      displaySegment = {
        type: TextSegmentType.VAR,
        varName: match[1]
      };
    } else {
      displaySegment = {
        type: TextSegmentType.TEXT,
        text: token
      };
    }
    return displaySegment;
  });
}
