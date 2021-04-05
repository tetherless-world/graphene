
const DEFAULT_VIEWS = Object.freeze({
  NEW: 'new',
  EDIT: 'edit',
  VIEW: 'view'
})

const VIEW_URIS = Object.freeze({
  CHART_EDITOR: "http://semanticscience.org/resource/Chart",
  SPARQL_TEMPLATES: "http://vocab.rpi.edu/whyis/SparqlTemplate"
})

function getCurrentUri () {
  return NODE_URI
}

function getCurrentView () {
  const params = new URLSearchParams(window.location.search)
  const view = params.get('view')
  return view
}

function getViewUrl(uri, view) {
  return `${ROOT_URL}about?view=${view || 'view'}&uri=${uri}`
}

function goToView(uri, view, args) {
  if(args){
    return window[args](getViewUrl(uri, view), '_blank')
  }
  return window.location = getViewUrl(uri, view)
}

export { DEFAULT_VIEWS, VIEW_URIS, getCurrentUri, getCurrentView, getViewUrl, goToView }
