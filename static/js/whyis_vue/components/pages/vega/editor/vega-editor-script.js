import Vue from 'vue'
import { mapState, mapGetters, mapMutations, mapActions } from 'vuex';
import splitPane from 'vue-splitpane'
import VJsoneditor from 'v-jsoneditor'
import { load } from 'js-yaml';

import { EventServices } from '../../../../modules'
import { goToView, VIEW_URIS, DEFAULT_VIEWS } from "../../../../utilities/views";
import { getDefaultChart, loadChart, saveChart, buildSparqlSpec } from 'utilities/vega-chart'
import { getCurrentView } from 'utilities/views'
import { querySparql } from 'utilities/sparql'

export default Vue.component('vega-editor', {
  props:['instances'],
  data() {
    return {
      loading: false,
      showAllTabBtn: false,
      showAllTabs: {display: 'none'},
      paneResize: 18,
      bottomPosition:'md-bottom-right',
      previewPane: true,
      authenticated: EventServices.authUser,
      restoredChartId: null,
      results: null,
      chartPub: null,
      specJsonEditorOpts: {
        mode: 'code',
        mainMenuBar: false
      },
      actionType: 'Save Chart'
    }
  },
  computed: {
    ...mapState('vizEditor', ['uri', 'baseSpec', 'query', 'title', 'description', 'depiction']),
    ...mapGetters('vizEditor', ['chart']),
    spec () {
      const spec = buildSparqlSpec(this.baseSpec, this.results)
      return spec
    }
  },
  components: {
    splitPane,
    VJsoneditor
  },
  methods: {
    ...mapActions('vizEditor', ['loadChart']),
    ...mapMutations('vizEditor', ['setBaseSpec', 'setQuery', 'setTitle', 'setDescription', 'setDepiction', 'setChart']),
    navBack() {
      return EventServices.navTo('view', true)
    },
    resize(e){
      if(e <= 26){
        this.showAllTabBtn = true;
      } else {
        this.showAllTabBtn = false;
      }
    },
    showTabNavigation(){
      this.paneResize = 50;
      this.showAllTabBtn = false;
      return this.paneResize = 18;
    },
    async tabNavigation(e){
      const sparql = document.getElementById('sparqlc')
      const vega = document.getElementById('vegac')
      const save = document.getElementById('savec')
      const tabs = await document.querySelectorAll('.viz-editor-tabs-item')
      if(tabs.length){
        tabs.forEach(el => el.classList.remove('tabselected'))
      }
      e.srcElement.classList.add('tabselected')
      if(e.srcElement.id == 'vegaE'){
        sparql.classList.remove('viz-editor-show')
        save.classList.remove('viz-editor-show')
        vega.classList.add('viz-editor-show')
      } else if(e.srcElement.id == 'saveE') {
        sparql.classList.remove('viz-editor-show')
        vega.classList.remove('viz-editor-show')
        save.classList.add('viz-editor-show')
      } else {
        save.classList.remove('viz-editor-show')
        vega.classList.remove('viz-editor-show')
        sparql.classList.add('viz-editor-show')
      }
    },
    async getSparqlData () {
      const results = await querySparql(this.query)
      this.onQuerySuccess(results)
    },
    onQuerySuccess (results) {
      this.results = results
    },
    onSpecJsonError () {
      console.log('bad', arguments)
    },
    async onNewVegaView (view) {
      const blob = await view.toImageURL('png')
        .then(url => fetch(url))
        .then(resp => resp.blob())
      const fr = new FileReader()
      fr.addEventListener('load', () => {
        this.setDepiction(fr.result)
      })
      fr.readAsDataURL(blob)
    },
    async initializeChart () {
      this.loading = true
      if (this.pageView === 'edit') {
        await loadChart(this.pageUri)
      } else if (this.pageView === 'restore'){
	      await this.postChartBk()
	      return this.getSparqlData()
      }
      await this.getSparqlData()
      this.loading = false
    },
    async reloadRestored(args){
      const currChart = EventServices.tempChart;
      if(currChart && currChart.chart){
        await ec.appState.filter(el => {
          if(el._id == currChart.chart._id) {
            el.restored = true;
          }
        })
      }
      const text = args == 'Editing' ? 'Edited' : 'Restored'
      EventServices.$emit('snacks', {status:true, message: `Chart ${text} Successfully`});
      //RELOAD RESTORE USED IN SETTINGS TO RE FILTER CHART LIST
      EventServices.$emit('reloadrestored', true)
      return EventServices.navTo('view', true);
    },
    async saveChart () {
      const vm = this;
      try {
        saveChart(this.chart)
        .then(async() => {
          if(vm.actionType == 'Restore' || vm.actionType == 'Editing'){
            const res = await EventServices.createBackUp(vm.chart, vm.restoredChartId, true, this.selectedTags);
            if(res.mssg){
              return vm.reloadRestored(vm.actionType);
            }
            return;
          } else {
            await EventServices.createBackUp(this.chart, null, true, this.selectedTags);
            EventServices.$emit('snacks', {status:true, message: 'Chart Saved Successfully'});
            return EventServices.navTo('view', true);
          }
        })
      } catch(err){
        //TODO USE THE APP DIALOGUE BOX INSTEAD OF ALERT BOX
        return alert(err)
      }
    },
    async postChartBk(){
      if (typeof(Storage) !== "undefined") {
        let recievedChart = await JSON.parse(sessionStorage.getItem("chart"));
        if(!recievedChart){
          return;
        } else {
          this.setChart(recievedChart.backup)
          this.restoredChartId = recievedChart.name
        }
      } else {
        EventServices.$emit('snacks', {status:true, message: 'No Browser Support!!!'});
      }
    },
    defineAction(){
      const thisView = getCurrentView();
      if(thisView == 'restore'){
        this.actionType = 'Restore';
      } else if (thisView == 'edit'){
        this.actionType = 'Editing';
      } else {
        this.actionType = 'Save Chart';
      }
    },
    goToSparqlTemplates() {
      goToView(VIEW_URIS.SPARQL_TEMPLATES)
    },
    goToDataVoyager() {
      goToView(VIEW_URIS.CHART_EDITOR, 'voyager')
    },
  },
  async created () {
    if(EventServices.authUser == undefined){
      return EventServices.navTo('view', true)
    }
    this.defineAction();
    this.initializeChart();
  }
})
