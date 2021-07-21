<template>
  <div class="sparql-template-page">
    <div v-if="loadingTemplates">
      <md-progress-spinner md-mode="indeterminate" />
    </div>
    <div v-else-if="totalTemplateCount === 0">
      <p>No templates were loaded</p>
    </div>
    <div v-else>
      <div class="button-row">
        <div>
          <md-button
            class="md-icon-button"
            @click.native.prevent="selectQueryForVizEditor()"
          >
            <md-tooltip
              class="utility-bckg"
              md-direction="bottom"
            >
              Select current query and return to Viz Editor
            </md-tooltip>
            <md-icon>check</md-icon>
          </md-button>
          <md-button
            class="md-icon-button"
            @click.native.prevent="toVizEditor()"
          >
            <md-tooltip
              class="utility-bckg"
              md-direction="bottom"
            > Return to viz editor </md-tooltip>
            <md-icon>arrow_back</md-icon>
          </md-button>
        </div>
      </div>
      <md-toolbar>
        <h3 class="md-title">Query Template</h3>
      </md-toolbar>
      <div class="display">
        <md-button
          class="template-back"
          @click="shiftTemplate(-1)"
        >
          <md-icon>chevron_left</md-icon>
        </md-button>
        <md-button
          class="template-next"
          @click="shiftTemplate(1)"
        >
          <md-icon>chevron_right</md-icon>
        </md-button>
        <p class="display-text">
          <span
            v-for="(segment, index) in selectedTemplate.displaySegments"
            :key="index"
          >
            <span
              v-if="segment.type == TextSegmentType.TEXT"
              v-html="segment.text"
            ></span>
            <span v-else>
              <select
                v-model="varSelections[segment.varName]"
                :id="segment.varName"
                :name="segment.varName"
              >
                <option
                  v-for="(value, name) in selectedTemplate.options[segment.varName]"
                  :key="name"
                  :value="name"
                >
                  {{name}}
                </option>
              </select>
            </span>
          </span>
        </p>
      </div>
      <div class="display-count-indicator">
        <p>Query template {{currentIndex + 1}} of {{totalTemplateCount}}</p>
      </div>
      <div
        class="query"
        v-if="query"
      >
        <accordion
          :startOpen="false"
          title="SPARQL Query"
        >
          <yasqe
            :value="query"
            readonly="true"
          ></yasqe>
        </accordion>
      </div>
      <div class="results">
        <accordion
          :startOpen="true"
          title="SPARQL Results"
        >
          <div v-if="results">
            <yasr :results="results"></yasr>
          </div>
          <md-progress-spinner
            v-else
            :md-diameter="30"
            :md-stroke="3"
            md-mode="indeterminate"
          ></md-progress-spinner>
        </accordion>
      </div>
    </div>
  </div>
</template>

<script>
import { mapMutations } from "vuex";
import { querySparql } from "../../../utilities/sparql";
import { goToView, VIEW_URIS, DEFAULT_VIEWS } from "../../../utilities/views";
import { loadSparqlTemplates, TextSegmentType, OptValueType } from "./load-sparql-templates";
import debounce from "../../../utilities/debounce";


const stripQVarFormatting = formatted =>
  formatted
    .replace(/^{{/, "")
    .replace(/}}$/, "")
    .trim();
const qVarRegex = /({{[^{}]+}})/g;


export default {
  data() {
    return {
      loadingTemplates: true,
      queryTemplates: {},
      TextSegmentType,
      selTemplateId: null,
      query: "",
      varSelections: {},
      results: null,
      execQueryDebounced: debounce(this.execQuery, 300)
    };
  },
  computed: {
    templateIds() {
      return Object.keys(this.queryTemplates);
    },
    selectedTemplate() {
      return this.queryTemplates[this.selTemplateId];
    },
    currentIndex() {
      return this.templateIds.indexOf(this.selTemplateId);
    },
    totalTemplateCount() {
      return this.templateIds.length;
    },
  },
  methods: {
    ...mapMutations("vizEditor", ["setQuery"]),
    selectQueryForVizEditor() {
      this.setQuery(this.query);
      this.toVizEditor();
    },
    toVizEditor() {
      goToView(VIEW_URIS.CHART_EDITOR, DEFAULT_VIEWS.NEW);
    },
    async loadSparqlTemplates() {
      this.loadingTemplates = true;
      try {
        const templates = await loadSparqlTemplates();
        this.queryTemplates = {}
        templates.forEach(t => this.queryTemplates[t.id] = t)
        console.log('qtemps', this.queryTemplates)
        this.selTemplateId = templates.length > 0 ? templates[0].id : null
      } finally {
        this.loadingTemplates = false;
      }
    },
    shiftTemplate(amount) {
      let newIndex = this.currentIndex + amount;
      while (newIndex >= this.totalTemplateCount) {
        newIndex -= this.totalTemplateCount;
      }
      while (newIndex < 0) {
        newIndex += this.totalTemplateCount;
      }
      this.selTemplateId = this.templateIds[newIndex];
      console.log("shifted", newIndex, this.selTemplateId, this.templateIds);
    },
    populateSelections() {
      if (!this.selectedTemplate) {
        return;
      }
      this.varSelections = Object.fromEntries(
        Object.entries(
          this.selectedTemplate.options
        ).map(([varName, varOpts]) => [varName, Object.keys(varOpts)[0]])
      );
    },
    getOptVal(varName, optName) {
      return this.selectedTemplate.options[varName][optName]
    },
    buildQuery() {
      if (!this.selectedTemplate) {
        return;
      }
      this.query = this.selectedTemplate.SPARQL

      this.selectedTemplate.options

      // append VALUES clause to query if there are any active selections
      const activeSelections = Object.fromEntries(
        Object.entries(this.varSelections)
          .filter(selEntry => this.getOptVal(...selEntry).type !== OptValueType.ANY)
      )
      if (Object.keys(activeSelections).length > 0) {
        const varNames = Object.keys(activeSelections)
          .map(varName => `?${varName}`)
          .join(" ")

        const optVals = Object.entries(activeSelections)
          .map( selEntry => {
            const optVal = this.getOptVal(...selEntry)
            let value
            if (optVal.type === OptValueType.LITERAL) {
              value = optVal.value
              if (typeof value !== "number") {
                value = `"${value}"`
              }
            } else if (optVal.type === OptValueType.IDENTIFIER) {
              value = `<${optVal.value}>`
            } else {
              throw `Unknown option value type: ${optVal.type}`
            }
            return value
          })
          .join(" ")

        this.query += `\nVALUES (${varNames}) {\n  (${optVals})\n}\n`
      }
    },
    async execQuery() {
      console.log("querying....");
      this.results = null;
      this.results = await querySparql(this.query);
      console.log("done", this.results);
    }
  },
  created() {
    this.loadSparqlTemplates();
  },
  watch: {
    // The following reactive watchers are used due to limitations of not being
    // able to deep watch dependencies of computed methods.
    selectedTemplate: {
      handler: "populateSelections"
    },
    varSelections: {
      handler: "buildQuery",
      deep: true
    },
    query: {
      handler: "execQueryDebounced"
    }
  }
};
</script>

<style lang="scss" scoped>
.sparql-template-page {
  max-width: 960px;
  margin: auto;
}
.display {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  height: 18em;
  .template-next {
    order: 1;
  }
  .display-text {
    max-height: calc(100% - 60px);
    overflow: auto;
    margin: 30px;
    font-size: 16px;
    line-height: 40px;
  }
}
.display-count-indicator {
  text-align: center;
  margin-bottom: 20px;
  font-weight: 500;
}
.accordion {
  margin-bottom: 20px;
}
</style>
