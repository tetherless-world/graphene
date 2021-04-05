import Vue from 'vue'
import Vuex from 'vuex'
import createPersistedState from 'vuex-persistedstate'

import vizEditor from './viz-editor'

Vue.use(Vuex)

export const store = new Vuex.Store({
  modules: {
    vizEditor
  },
  plugins: [createPersistedState()],
})
