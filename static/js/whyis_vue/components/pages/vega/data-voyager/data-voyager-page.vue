
<template>
  <div>
    <div class="utility-content__result">
      <div
        class="utility-gridicon-single"
        v-if="!loading"
      >
        <div>
          <md-button
            class="md-icon-button"
            @click.native.prevent="saveAsChart"
            v-if="!isNewChart && voyagerSpec"
          >
            <md-tooltip
              class="utility-bckg"
              md-direction="bottom"
            >
              Save current spec as new chart
            </md-tooltip>
            <md-icon>save</md-icon>
          </md-button>
          <md-button
            class="md-icon-button"
            @click.native.prevent="selectSpec"
            v-if="isNewChart && voyagerSpec"
          >
            <md-tooltip
              class="utility-bckg"
              md-direction="bottom"
            >
              Select current spec and return to Viz Editor
            </md-tooltip>
            <md-icon>check</md-icon>
          </md-button>
          <md-button
            class="md-icon-button"
            @click.native.prevent="goToChartView"
          >
            <md-tooltip
              class="utility-bckg"
              md-direction="bottom"
            > Return to chart view </md-tooltip>
            <md-icon>arrow_back</md-icon>
          </md-button>
        </div>
      </div>
    </div>
    <div class="viz-sample__header viz-u-mgbottom">
      <span class="dv-title">Data Voyager</span>
      <span v-if="!isNewChart && chart && chart.title">: {{chart.title}}</span>
    </div>
    <div
      class="loading-dialog"
      style="margin: auto"
      v-if="loading"
    >
      <spinner :loading="loading" />
    </div>
    <div
      class="loading-dialog"
      style="margin: auto"
      v-else
    >
      <data-voyager
        :data="data"
        v-bind:spec.sync="voyagerSpec"
      ></data-voyager>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapActions, mapMutations } from 'vuex';
import { Slug } from "../../../../modules";
import {
  copyChart,
  saveChart,
  transformSparqlData
} from "../../../../utilities/vega-chart";
import { querySparql } from "../../../../utilities/sparql";
import { DEFAULT_VIEWS, VIEW_URIS, goToView } from "../../../../utilities/views";

export default {
  data() {
    return {
      loading: true,
      voyagerSpec: null,
      specJsonEditorOpts: {
        mode: "code",
        mainMenuBar: false
      }
    };
  },
  computed: {
    ...mapGetters('vizEditor', ['chart']),
    isNewChart () {
      return this.pageUri === VIEW_URIS.CHART_EDITOR
    },
  },
  methods: {
    ...mapActions('vizEditor', ['loadChart']),
    ...mapMutations('vizEditor', ['setBaseSpec']),
    slugify: Slug,
    async loadData() {
      this.loading = true;
      if (!this.isNewChart) {
        await this.loadChart()
      }
      const sparqlResults = await querySparql(this.chart.query);
      this.data = { values: transformSparqlData(sparqlResults) };
      this.loading = false
    },
    saveAsChart() {
      this.loading = true;
      const newChart = copyChart(this.chart);
      newChart.title = `DataVoyager Variant: ${newChart.title}`;
      newChart.baseSpec = this.voyagerSpec;
      console.log(newChart);
      delete newChart.depiction;
      saveChart(newChart).then(() =>
        goToView(newChart.uri, DEFAULT_VIEWS.EDIT)
      );
    },
    selectSpec() {
      this.setBaseSpec(this.voyagerSpec)
      this.goToChartEditor()
    },
    goToChartView() {
      goToView(this.pageUri, DEFAULT_VIEWS.VIEW);
    },
    goToChartEditor() {
      goToView(VIEW_URIS.CHART_EDITOR, DEFAULT_VIEWS.NEW);
    },
    goBack() {
      if (this.isNewChart) {
        this.goToChartEditor()
      } else {
        this.goToChartView()
      }
    }
  },
  mounted() {
    this.loadData();
  }
};
</script>

<style scoped lang="scss" src="../../../../assets/css/main.scss"></style>

<style scoped>
.dv-title {
  font-weight: 500;
}
.utility-gridicon-single {
  top: 0.5rem;
}
</style>

<style>
#voyager-embed {
  background: #fafafa;
  height: 100%;
  width: calc(100% - 2.6rem);
  margin: 30px 1.3rem;
}
</style>
