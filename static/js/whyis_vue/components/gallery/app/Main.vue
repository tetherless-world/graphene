<template>
  <div>
    <div v-if="loading">
      <spinner :loading="loading" :text='loadingText'/>
    </div>
    <div v-else>
      <viz-grid :authenticated="authenticated" :instancetype="instancetype"/>
      <md-speed-dial :class="bottomPosition">
        <md-speed-dial-target class="utility-float-icon">
          <md-icon>menu</md-icon>
        </md-speed-dial-target>

        <md-speed-dial-content>
          <md-button class="md-icon-button" @click="cancelFilter">
            <md-tooltip class="utility-bckg" md-direction="left"> Cancel Filter </md-tooltip>
            <md-icon class="utility-color">search_off</md-icon>
          </md-button>
          <md-button class="md-icon-button" @click="showFilterBox">
            <md-tooltip class="utility-bckg" md-direction="left"> Filter </md-tooltip>
            <md-icon class="utility-color">search</md-icon>
          </md-button>
        </md-speed-dial-content>
      </md-speed-dial>
    </div>
  </div>
</template>
<style scoped lang="scss" src="../../../assets/css/main.scss"></style>
<script>
  import Vue from 'vue'
  import EventServices from '../../../modules/events/event-services'
  import vizGrid from './components/Vizgrid'
  export default Vue.component('viz-gallery', {
    props:{
      instancetype: {
        type: String,
        require: true
      }
    },
    data() {
      return {
        filter: false,
        bottomPosition:'md-bottom-right',
        speedDials: EventServices.speedDials,
        authenticated: EventServices.authUser,
        charts:[],
        loading: false,
        loadingText: "loading up..."
      }
    },
    components: {
      vizGrid,
    },
    methods: {
      showFilterBox () {
        // EventServices.$emit('open-filter-box', {open: true, type: "filter"});
        // return this.filter = true
      },
      cancelFilter(){
        // return EventServices.cancelChartFilter();
      }
    },
    created() {
      EventServices
      .$on('close-filter-box', (data) => this.filter = data)
      .$on('isauthenticated', (data) => this.authenticated = data)
    }
  })
</script>
