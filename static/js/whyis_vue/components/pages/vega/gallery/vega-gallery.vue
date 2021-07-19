<template>
  <div>
    <div v-if="existingBkmk.status">
      <spinner :loading="existingBkmk.status" :text='existingBkmk.text'/>
    </div>
    <div v-else>
      <viz-grid :authenticated="authenticated" :instancetype="'http://semanticscience.org/resource/Chart'"/>
      <md-speed-dial :class="bottomPosition" v-if="speedDials">
        <md-speed-dial-target class="utility-float-icon">
          <md-icon>menu</md-icon>
        </md-speed-dial-target>

        <md-speed-dial-content>
          <md-button class="md-icon-button" @click.prevent="cancelFilter">
            <md-tooltip class="utility-bckg" md-direction="left"> Cancel Filter </md-tooltip>
            <md-icon class="utility-color">search_off</md-icon>
          </md-button>
          <md-button class="md-icon-button" @click="showFilterBox">
            <md-tooltip class="utility-bckg" md-direction="left"> Filter </md-tooltip>
            <md-icon class="utility-color">search</md-icon>
          </md-button>
          <md-button class="md-icon-button" @click.prevent="showIntro(true)">
            <md-tooltip class="utility-bckg" md-direction="left">Replay Tips</md-tooltip>
            <md-icon class="utility-color">info</md-icon>
          </md-button>
          <md-button class="md-icon-button" v-if="authenticated !== undefined" @click.prevent="newChart">
            <md-tooltip class="utility-bckg" md-direction="left">Create New Chart</md-tooltip>
            <md-icon class="utility-color">add</md-icon>
          </md-button>
        </md-speed-dial-content>
      </md-speed-dial>
    </div>
  </div>
</template>
<style scoped lang="scss" src="../../../../assets/css/main.scss"></style>
<script>
  import Vue from 'vue';
  import vizGrid from '../../../gallery/app/components/Vizgrid';
  import { EventServices } from '../../../../modules';
  export default Vue.component('vega-gallery', {
    data() {
      return {
        filter: false,
        bottomPosition:'md-bottom-right',
        speedDials: EventServices.speedDials,
        authenticated: EventServices.authUser,
        existingBkmk: {
          status: false
        }
      }
    },
    components: {
      vizGrid
    },
    mounted() {
      return this.showIntro();
    },
    methods: {
      showIntro(arg){
        return EventServices.tipController(arg)
      },
      showFilterBox () {
        EventServices.$emit('open-filter-box', {open: true, type: "filter"});
        return this.filter = true
      },
      newChart(){
        return EventServices.navTo("new", true)
      },
      cancelFilter(){
        return EventServices.cancelChartFilter();
      }
    },
    created() {
      EventServices
      .$on('close-filter-box', (data) => this.filter = data)
      .$on('isauthenticated', (data) => this.authenticated = data)
      .$on('gotexistingbookmarks', data => this.existingBkmk = data)
    }
  })
</script>
