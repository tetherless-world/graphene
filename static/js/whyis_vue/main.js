import Vue from 'vue'
import * as VueMaterial from 'vue-material'
import axios from 'axios'
import './modules'
import './components'
import {store} from './store'
import Header from './components/utils/header'
import Drawer from './components/utils/drawer'
// import dialogBox from './components/utils/dialog'
import viewMixin from './mixins/view-mixin'

Vue.use(VueMaterial.default)
Vue.mixin(viewMixin)

let data = {}
if (typeof (ATTRIBUTES) !== 'undefined') {
  data = {
    attributes: ATTRIBUTES,
    uri: NODE_URI,
    description: DESCRIPTION,
    user: USER,
    node: NODE,
    root_url: ROOT_URL,
    base_rate: BASE_RATE,
    lod_prefix: LOD_PREFIX,
    axios: axios,
  }
}

new Vue({
  el: '#page',
  data,
  store,
  components: {
    mdAppToolbar: Header,
    mdAppDrawer: Drawer,
    // dialogBox
  }
})
