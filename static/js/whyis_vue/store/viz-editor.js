import { getDefaultChart, loadChart, saveChart, buildSparqlSpec } from '../utilities/vega-chart'

const state = () => getDefaultChart()

const actions = {
  resetChart({commit}) {
    commit('setChart', getDefaultChart())
  },
  async loadChart({commit}, uri) {
    const chart = await loadChart(uri)
    commit('setChart', chart)
  }
}

const getters = {
  chart(state) {
    return state
  }
}

const mutations = {
  setBaseSpec(state, baseSpec) {
    state.baseSpec = baseSpec
  },
  setQuery(state, query) {
    state.query = query
  },
  setTitle(state, title) {
    state.title = title
  },
  setDescription(state, description) {
    state.description = description
  },
  setDepiction(state, depiction) {
    state.depiction = depiction
  },
  setChart(state, chart) {
    Object.assign(state, chart)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
