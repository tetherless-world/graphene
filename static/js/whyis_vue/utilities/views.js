
const DEFAULT_VIEWS = Object.freeze({
  NEW: 'new',
  EDIT: 'edit',
  VIEW: 'view'
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
    if (view != null) {
        return `${ROOT_URL}about?view=${view}&uri=${uri}`
    }
    else {
        return `${ROOT_URL}about?uri=${uri}`
    }
}

function goToView(uri, view, args) {
  if(args){
    return window[args](getViewUrl(uri, view), '_blank')
  }
  return window.location = getViewUrl(uri, view)
}

export { DEFAULT_VIEWS, getCurrentUri, getCurrentView, getViewUrl, goToView }
